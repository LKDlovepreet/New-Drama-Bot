import os

def render_template(subfolder, filename, **kwargs):
    # subfolder jaise 'templates', 'admin/templates', 'user/templates'
    filepath = os.path.join("dashboard", subfolder, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    for key, value in kwargs.items():
        content = content.replace(f"{{{key}}}", str(value))
    return content
