"""
iNetCDF - NetCDF file inspector for iOS
"""
import toga
from toga.style.pack import COLUMN, Pack

try:
    import ncreader as nc
    HAS_NETCDF = True
except ImportError:
    HAS_NETCDF = False


def ncdump_h(filepath):
    """Produce ncdump -h style output from a NetCDF file."""
    if not HAS_NETCDF:
        return "[netCDF4 not available — using pure Python reader]"
    
    with nc.Dataset(filepath, 'r') as ds:
        lines = []
        lines.append(f"netcdf {filepath} {{")
        lines.append("dimensions:")
        for name, dim in ds.dimensions.items():
            size = f"{len(dim)} // UNLIMITED" if dim.isunlimited() else str(len(dim))
            lines.append(f"\t{name} = {size} ;")
        lines.append("variables:")
        for name, var in ds.variables.items():
            dims = ", ".join(var.dimensions)
            lines.append(f"\t{var.dtype} {name}({dims}) ;")
            for attr in var.ncattrs():
                val = getattr(var, attr)
                lines.append(f"\t\t{name}:{attr} = {val!r} ;")
        lines.append("\n// global attributes:")
        for attr in ds.ncattrs():
            val = getattr(ds, attr)
            lines.append(f"\t\t:{attr} = {val!r} ;")
        lines.append("}")
        return "\n".join(lines)


class iNetCDF(toga.App):
    def startup(self):
        self.output = toga.MultilineTextInput(
            readonly=True,
            style=Pack(flex=1, font_family="monospace", font_size=11)
        )

        open_btn = toga.Button(
            "Open .nc File",
            on_press=self.open_file,
            style=Pack(padding=10)
        )

        main_box = toga.Box(
            children=[open_btn, self.output],
            style=Pack(direction=COLUMN, flex=1)
        )

        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = main_box
        self.main_window.show()

    def open_file(self, widget):
        try:
            from rubicon.objc import ObjCClass, objc_method, NSObject
            from rubicon.objc.types import NSInteger

            UIDocumentPickerViewController = ObjCClass(
                "UIDocumentPickerViewController"
            )
            NSArray = ObjCClass("NSArray")
            NSURL = ObjCClass("NSURL")

            # UTType for public data / any file
            utypes = NSArray.arrayWithObject("public.data")

            picker = UIDocumentPickerViewController.alloc(
            ).initWithDocumentTypes(utypes, inMode=0)
            picker.allowsMultipleSelection = False

            # Delegate to receive result
            iNetCDFDelegate = self._make_delegate()
            self._delegate = iNetCDFDelegate
            picker.delegate = iNetCDFDelegate

            # Present picker
            UIApplication = ObjCClass("UIApplication")
            root_vc = (
                UIApplication.sharedApplication
                .keyWindow
                .rootViewController
            )
            root_vc.presentViewController(
                picker, animated=True, completion=None
            )

        except Exception as e:
            self.output.value = f"Error opening picker:\n{e}"

    def _make_delegate(self):
        from rubicon.objc import ObjCClass, objc_method, NSObject

        app_ref = self

        class PickerDelegate(NSObject):
            @objc_method
            def documentPicker_didPickDocumentsAtURLs_(
                self, controller, urls
            ):
                url = urls[0]
                path = str(url.path)
                try:
                    app_ref.output.value = ncdump_h(path)
                except Exception as e:
                    app_ref.output.value = f"Error reading file:\n{e}"

            @objc_method
            def documentPickerWasCancelled_(self, controller):
                pass

        return PickerDelegate.alloc().init()


def main():
    return iNetCDF()