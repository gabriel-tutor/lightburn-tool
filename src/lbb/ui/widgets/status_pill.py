from PySide6.QtWidgets import QLabel


class StatusPill(QLabel):
    """A one-line LightBurn connection indicator.

    Sets its objectName to 'statusOk' / 'statusError' so the QSS theme can
    color it appropriately.
    """

    def __init__(self) -> None:
        super().__init__("● LightBurn — Not connected")
        self.setObjectName("statusError")

    def set_running(self, running: bool) -> None:
        if running:
            self.setText("● LightBurn — Ready")
            self.setObjectName("statusOk")
        else:
            self.setText("● LightBurn — Not connected")
            self.setObjectName("statusError")
        # Re-apply QSS after objectName change.
        self.style().unpolish(self)
        self.style().polish(self)
