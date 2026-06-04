from pydantic import BaseModel

class DeviceInfo(BaseModel):
    device_type: str | None = None
    os_name: str | None = None
    os_version: str | None = None
    browser_name: str | None = None
    browser_version: str | None = None
    ip_address: str | None = None