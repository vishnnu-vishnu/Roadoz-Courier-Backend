import io
import base64

import barcode
from barcode.writer import ImageWriter


def generate_barcode_base64(data: str) -> str:
    """Generate a Code128 barcode PNG and return it as a base64-encoded string."""
    code128 = barcode.get_barcode_class("code128")
    writer = ImageWriter()
    writer.set_options({"module_width": 0.4, "module_height": 15.0, "quiet_zone": 6.5})

    barcode_obj = code128(data, writer=writer)

    buffer = io.BytesIO()
    barcode_obj.write(buffer, options={"write_text": True})
    buffer.seek(0)

    return base64.b64encode(buffer.read()).decode("utf-8")
