import base64
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from jinja2 import Environment, FileSystemLoader

class HTMLExportService:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent.parent
        self.template_dir = self.base_dir / "app" / "templates"
        self.static_dir = self.base_dir / "app" / "static"  # Or wherever css is
        # Adjust paths based on my previous creation
        self.css_path = self.template_dir / "css" / "style.css"
        self.logo_path = self.base_dir.parent / "frontend" / "public" / "assets" / "darklogo.png"
        
        self.env = Environment(loader=FileSystemLoader(str(self.template_dir)))

    def _get_base64_image(self, image_path: Path) -> Optional[str]:
        if not image_path.exists():
            return None
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            print(f"Error loading image {image_path}: {e}")
            return None

    def _get_css_content(self) -> str:
        if not self.css_path.exists():
            return "/* CSS file not found */"
        try:
            with open(self.css_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"/* Error loading CSS: {e} */"

    def _sanitize_data(self, data: Any) -> Any:
        """
        Recursively sanitize data to ensure it's JSON serializable/template friendly.
        Removes complex objects like LangGraph AddableValuesDict that might cause issues.
        """
        if isinstance(data, dict):
            # Convert special dict types to standard dict
            return {k: self._sanitize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_data(v) for v in data]
        elif isinstance(data, (str, int, float, bool, type(None))):
            return data
        else:
            # For other types (like AddableValuesDict, objects, etc.), try to convert to string
            # or just return string representation to be safe
            try:
                # Try to see if it has a dict representation
                if hasattr(data, "dict"):
                    return self._sanitize_data(data.dict())
                if hasattr(data, "__dict__"):
                    return self._sanitize_data(data.__dict__)
                return str(data)
            except:
                return str(data)

    def generate_html(self, result_data: Dict[str, Any]) -> str:
        """
        Generates the HTML string from the result data.
        """
        # Sanitize data first to prevent serialization errors
        safe_result = self._sanitize_data(result_data)
        
        template = self.env.get_template("output.html")
        
        css_content = self._get_css_content()
        logo_base64 = self._get_base64_image(self.logo_path)
        
        # Ensure timestamp exists
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Render template
        html_content = template.render(
            result=safe_result,
            css_content=css_content,
            logo_base64=logo_base64,
            timestamp=timestamp
        )
        
        return html_content

    def save_html(self, result_data: Dict[str, Any], output_dir: str = "exports") -> str:
        """
        Generates and saves the HTML file. Returns the absolute path.
        """
        html_content = self.generate_html(result_data)
        
        result_id = result_data.get("result_id", "unknown_result")
        filename = f"{result_id}.html"
        
        # Create output directory if not exists
        out_path = Path(output_dir)
        if not out_path.is_absolute():
            # Force resolve relative path against base_dir to ensure it's correct
            out_path = (self.base_dir / output_dir).resolve()
            
        try:
            out_path.mkdir(parents=True, exist_ok=True)
            print(f"Directory ensured: {out_path}")
        except Exception as e:
            print(f"Failed to create directory {out_path}: {e}")
            raise
        
        file_path = out_path / filename
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"File saved successfully: {file_path}")
        except Exception as e:
            print(f"Failed to write file {file_path}: {e}")
            raise
            
        return str(file_path)

# Singleton instance
html_export_service = HTMLExportService()
