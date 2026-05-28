"""
iNetCDF - NetCDF file inspector for iOS
"""
import toga
from toga.style.pack import COLUMN, ROW, Pack

try:
    import ncreader as nc
    HAS_NETCDF = True
except ImportError:
    HAS_NETCDF = False


def ncdump_h(filepath):
    """Produce ncdump -h style output from a NetCDF file."""
    if not HAS_NETCDF:
        return "[netCDF3 not available in this environment]"
    
    with nc.Dataset(filepath, 'r') as ds:
        lines = []
        lines.append(f"netcdf {filepath} {{")
        
        # Dimensions
        lines.append("dimensions:")
        for name, dim in ds.dimensions.items():
            size = f"{len(dim)} // UNLIMITED" if dim.isunlimited() else str(len(dim))
            lines.append(f"\t{name} = {size} ;")
        
        # Variables
        lines.append("variables:")
        for name, var in ds.variables.items():
            dims = ", ".join(var.dimensions)
            lines.append(f"\t{var.dtype} {name}({dims}) ;")
            for attr in var.ncattrs():
                val = getattr(var, attr)
                lines.append(f"\t\t{name}:{attr} = {val!r} ;")
        
        # Global attributes
        lines.append("\n// global attributes:")
        for attr in ds.ncattrs():
            val = getattr(ds, attr)
            lines.append(f"\t\t:{attr} = {val!r} ;")
        
        lines.append("}")
        return "\n".join(lines)


class iNetCDF(toga.App):
    def startup(self):
        # Output text area
        self.output = toga.MultilineTextInput(
            readonly=True,
            style=Pack(flex=1, font_family="monospace", font_size=11)
        )

        # Open file button
        open_btn = toga.Button(
            "Open .nc File",
            on_press=self.open_file,
            style=Pack(padding=10)
        )

        # Layout
        main_box = toga.Box(
            children=[open_btn, self.output],
            style=Pack(direction=COLUMN, flex=1)
        )

        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box
        self.main_window.show()

    async def open_file(self, widget):
        try:
            dialog = toga.OpenFileDialog(
                title="Select a NetCDF file",
                file_types=["nc", "nc4", "netcdf"]
            )
            path = await self.main_window.dialog(dialog)
            if path:
                self.output.value = ncdump_h(str(path))
        except Exception as e:
            self.output.value = f"Error: {e}"


def main():
    return iNetCDF()