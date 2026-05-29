"""
NetCDF reader for iNetCDF.
On iOS: uses ctypes against bundled libnetcdf.dylib
On desktop: falls back to netCDF4 Python package for testing
"""
import ctypes
import os
import sys

# ── Library loading ───────────────────────────────────────────────────────────

def _load_lib():
    exe    = sys.executable
    bundle = os.path.dirname(os.path.dirname(exe))
    candidates = [
        os.path.join(bundle, "Frameworks", "libnetcdf.dylib"),
        os.path.join(os.path.dirname(__file__), "libnetcdf.dylib"),
        "libnetcdf.dylib",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ctypes.CDLL(path)
    raise OSError(f"libnetcdf.dylib not found. Searched:\n" +
                  "\n".join(candidates))


_lib       = None
_lib_error = None

try:
    _lib = _load_lib()
except OSError as e:
    _lib_error = str(e)

# ── NetCDF constants ──────────────────────────────────────────────────────────

NC_BYTE   = 1;  NC_CHAR   = 2;  NC_SHORT  = 3
NC_INT    = 4;  NC_FLOAT  = 5;  NC_DOUBLE = 6
NC_UBYTE  = 7;  NC_USHORT = 8;  NC_UINT   = 9
NC_INT64  = 10; NC_UINT64 = 11; NC_STRING = 12

NC_MAX_NAME = 256
NC_GLOBAL   = -1

TYPE_NAMES = {
    NC_BYTE: 'byte',   NC_CHAR: 'char',    NC_SHORT: 'short',
    NC_INT:  'int',    NC_FLOAT: 'float',  NC_DOUBLE: 'double',
    NC_UBYTE:'ubyte',  NC_USHORT:'ushort', NC_UINT:  'uint',
    NC_INT64:'int64',  NC_UINT64:'uint64', NC_STRING:'string',
}

TYPE_CTYPES = {
    NC_BYTE:   ctypes.c_int8,   NC_SHORT:  ctypes.c_int16,
    NC_INT:    ctypes.c_int32,  NC_FLOAT:  ctypes.c_float,
    NC_DOUBLE: ctypes.c_double, NC_UBYTE:  ctypes.c_uint8,
    NC_USHORT: ctypes.c_uint16, NC_UINT:   ctypes.c_uint32,
    NC_INT64:  ctypes.c_int64,  NC_UINT64: ctypes.c_uint64,
}

NUMPY_TO_CDL = {
    'float32': 'float',
    'float64': 'double',
    'int8':    'byte',
    'int16':   'short',
    'int32':   'int',
    'int64':   'int64',
    'uint8':   'ubyte',
    'uint16':  'ushort',
    'uint32':  'uint',
    'uint64':  'uint64',
    'S1':      'char',
}

# ── ctypes helpers ────────────────────────────────────────────────────────────

def _check(ret, op=""):
    if ret != 0:
        if _lib:
            _lib.nc_strerror.restype = ctypes.c_char_p
            msg = _lib.nc_strerror(ret).decode()
        else:
            msg = f"error code {ret}"
        raise RuntimeError(f"NetCDF error in {op}: {msg}")


def _read_att(ncid, varid, aname):
    atype  = ctypes.c_int()
    alen   = ctypes.c_size_t()
    name_b = aname.encode()
    _lib.nc_inq_att(ncid, varid, name_b,
                    ctypes.byref(atype), ctypes.byref(alen))
    t = atype.value
    n = alen.value

    if t == NC_CHAR:
        buf = ctypes.create_string_buffer(n + 1)
        _lib.nc_get_att_text(ncid, varid, name_b, buf)
        return buf.value.decode('utf-8', errors='replace')

    if t == NC_STRING:
        ptrs = (ctypes.c_char_p * n)()
        _lib.nc_get_att_string(ncid, varid, name_b, ptrs)
        return [p.decode() if p else '' for p in ptrs]

    ctype = TYPE_CTYPES.get(t)
    if ctype is None:
        return f"<unsupported type {t}>"

    getters = {
        NC_BYTE:   _lib.nc_get_att_schar,
        NC_SHORT:  _lib.nc_get_att_short,
        NC_INT:    _lib.nc_get_att_int,
        NC_FLOAT:  _lib.nc_get_att_float,
        NC_DOUBLE: _lib.nc_get_att_double,
        NC_UBYTE:  _lib.nc_get_att_ubyte,
        NC_USHORT: _lib.nc_get_att_ushort,
        NC_UINT:   _lib.nc_get_att_uint,
        NC_INT64:  _lib.nc_get_att_longlong,
        NC_UINT64: _lib.nc_get_att_ulonglong,
    }
    buf = (ctype * n)()
    fn  = getters.get(t)
    if fn:
        fn(ncid, varid, name_b, buf)
    vals = list(buf)
    return vals[0] if n == 1 else vals


def _fmt_val(val):
    if isinstance(val, str):
        return f'"{val}"'
    if isinstance(val, list):
        return ", ".join(_fmt_val(v) for v in val)
    if isinstance(val, float):
        return f"{val}f"
    return str(val)

def _fmt_att_val(val):
    """Format an attribute value to match ncdump output style."""
    import numpy as np

    # Unwrap numpy scalars to plain Python
    if isinstance(val, np.generic):
        val = val.item()

    if isinstance(val, str):
        escaped = val.replace('"', '\\"')
        return f'"{escaped}"'

    if isinstance(val, float):
        s = repr(val)
        if '.' not in s and 'e' not in s:
            s = s + '.'
        elif s.endswith('.0'):
            s = s[:-1]  # 6378137.0 → 6378137.
        return s

    if isinstance(val, int):
        return str(val)

    # numpy arrays or lists of numbers
    if isinstance(val, (list, tuple)) or (
        hasattr(val, '__iter__') and not isinstance(val, str)
    ):
        items = []
        for v in val:
            if isinstance(v, np.generic):
                v = v.item()
            items.append(_fmt_att_val(v))
        return ", ".join(items)

    return str(val)

# ── ctypes implementation ─────────────────────────────────────────────────────

def _ncdump_ctypes(filepath):
    ncid    = ctypes.c_int()
    ndims   = ctypes.c_int()
    nvars   = ctypes.c_int()
    natts   = ctypes.c_int()
    unlimid = ctypes.c_int()
    fmt     = ctypes.c_int()

    ret = _lib.nc_open(filepath.encode(), 0, ctypes.byref(ncid))
    _check(ret, "nc_open")

    try:
        _lib.nc_inq(ncid, ctypes.byref(ndims), ctypes.byref(nvars),
                    ctypes.byref(natts), ctypes.byref(unlimid))
        _lib.nc_inq_format(ncid, ctypes.byref(fmt))

        lines = [f"netcdf {os.path.basename(filepath)} {{"]

        # Dimensions
        lines.append("dimensions:")
        for i in range(ndims.value):
            name_buf = ctypes.create_string_buffer(NC_MAX_NAME + 1)
            length   = ctypes.c_size_t()
            _lib.nc_inq_dim(ncid, i, name_buf, ctypes.byref(length))
            name = name_buf.value.decode()
            size = length.value
            if i == unlimid.value:
                lines.append(
                    f"\t{name} = UNLIMITED ; // ({size} currently)")
            else:
                lines.append(f"\t{name} = {size} ;")

        # Variables
        lines.append("variables:")
        for v in range(nvars.value):
            vname_buf = ctypes.create_string_buffer(NC_MAX_NAME + 1)
            xtype     = ctypes.c_int()
            vndims    = ctypes.c_int()
            dimids    = (ctypes.c_int * 64)()
            vnatts    = ctypes.c_int()
            _lib.nc_inq_var(ncid, v, vname_buf, ctypes.byref(xtype),
                            ctypes.byref(vndims), dimids,
                            ctypes.byref(vnatts))
            vname    = vname_buf.value.decode()
            type_str = TYPE_NAMES.get(xtype.value, f"type{xtype.value}")

            dim_names = []
            for di in range(vndims.value):
                dname_buf = ctypes.create_string_buffer(NC_MAX_NAME + 1)
                _lib.nc_inq_dimname(ncid, dimids[di], dname_buf)
                dim_names.append(dname_buf.value.decode())

            dims_str = f"({', '.join(dim_names)})" if dim_names else ""
            lines.append(f"\t{type_str} {vname}{dims_str} ;")

            for a in range(vnatts.value):
                aname_buf = ctypes.create_string_buffer(NC_MAX_NAME + 1)
                _lib.nc_inq_attname(ncid, v, a, aname_buf)
                aname = aname_buf.value.decode()
                val   = _read_att(ncid, v, aname)
                lines.append(f"\t\t{vname}:{aname} = {_fmt_val(val)} ;")

        # Global attributes
        lines.append("\n// global attributes:")
        for a in range(natts.value):
            aname_buf = ctypes.create_string_buffer(NC_MAX_NAME + 1)
            _lib.nc_inq_attname(ncid, NC_GLOBAL, a, aname_buf)
            aname = aname_buf.value.decode()
            val   = _read_att(ncid, NC_GLOBAL, aname)
            lines.append(f"\t\t:{aname} = {_fmt_val(val)} ;")

        lines.append("}")
        return "\n".join(lines)

    finally:
        _lib.nc_close(ncid)

# ── netCDF4 fallback (desktop testing) ────────────────────────────────────────

def _ncdump_netcdf4(filepath):
    import netCDF4 as nc
    import numpy as np

    with nc.Dataset(filepath, 'r') as ds:
        lines = [f"netcdf {os.path.basename(filepath)} {{"]

        # Dimensions
        lines.append("dimensions:")
        for name, dim in ds.dimensions.items():
            if dim.isunlimited():
                lines.append(
                    f"\t{name} = UNLIMITED ; // ({len(dim)} currently)")
            else:
                lines.append(f"\t{name} = {len(dim)} ;")

        # Variables
        lines.append("variables:")
        for name, var in ds.variables.items():
            # CDL type name
            dtype_str = str(var.dtype)
            cdl_type  = NUMPY_TO_CDL.get(dtype_str, dtype_str)

            # Scalar variables have no parentheses
            if var.dimensions:
                dims_str = f"({', '.join(var.dimensions)})"
            else:
                dims_str = ""

            lines.append(f"\t{cdl_type} {name}{dims_str} ;")

            for attr in var.ncattrs():
                val = var.getncattr(attr)
                lines.append(
                    f"\t\t{name}:{attr} = {_fmt_att_val(val)} ;")

        # Global attributes
        lines.append("\n// global attributes:")
        for attr in ds.ncattrs():
            val = ds.getncattr(attr)
            lines.append(f"\t\t:{attr} = {_fmt_att_val(val)} ;")

        lines.append("}")
        return "\n".join(lines)

# ── Public API ────────────────────────────────────────────────────────────────

def ncdump_h(filepath):
    """Return ncdump -h style string for a NetCDF file."""
    if _lib is not None:
        return _ncdump_ctypes(filepath)
    # Fall back to netCDF4 package (desktop / CI testing)
    try:
        return _ncdump_netcdf4(filepath)
    except ImportError:
        return (
            f"Cannot read file.\n\n"
            f"libnetcdf.dylib not found:\n{_lib_error}\n\n"
            f"netCDF4 Python package also not available."
        )