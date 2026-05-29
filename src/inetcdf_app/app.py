"""
iNetCDF - NetCDF file inspector for iOS
"""
import toga
from toga.style.pack import COLUMN, Pack


def ncdump_h(filepath):
    try:
        from ncreader import ncdump_h as _ncdump_h
        return _ncdump_h(filepath)
    except Exception as e:
        return f"Error reading file:\n{type(e).__name__}: {e}"


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

            UIDocumentPickerViewController = ObjCClass(
                "UIDocumentPickerViewController"
            )
            NSArray = ObjCClass("NSArray")

            utypes = NSArray.arrayWithObject("public.data")
            picker = UIDocumentPickerViewController.alloc(
            ).initWithDocumentTypes(utypes, inMode=0)
            picker.allowsMultipleSelection = False

            self._delegate = self._make_delegate()
            picker.delegate = self._delegate

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
            self.output.value = f"Error opening file picker:\n{e}"

    def _make_delegate(self):
        from rubicon.objc import objc_method, NSObject

        app_ref = self

        class PickerDelegate(NSObject):

            @objc_method
            def documentPicker_didPickDocumentsAtURLs_(
                self, controller, urls
            ):
                controller.dismissViewControllerAnimated(
                    True, completion=None
                )
                url  = urls[0]
                path = str(url.path)
                app_ref.output.value = ncdump_h(path)

            @objc_method
            def documentPickerWasCancelled_(self, controller):
                controller.dismissViewControllerAnimated(
                    True, completion=None
                )

        return PickerDelegate.alloc().init()


def main():
    return iNetCDF()