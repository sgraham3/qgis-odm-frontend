# AGENTS.md - ODM Frontend Plugin Guidelines

This document provides guidelines for coding agents working on the ODM Frontend QGIS plugin. Follow these conventions to maintain consistency and quality.

## Build/Lint/Test Commands

### Syntax Checking
```bash
# Check Python syntax for all plugin files
python -m py_compile odm_dialog.py
python -m py_compile odm_plugin.py
python -m py_compile odm_connection.py
python -m py_compile __init__.py

# Check all Python files at once
find . -name "*.py" -exec python -m py_compile {} \;
```

### Plugin Development
- **No build system**: This is a QGIS plugin loaded directly into QGIS
- **Testing**: Manual testing in QGIS environment only
- **Linting**: Use Python's built-in syntax checking (`py_compile`)
- **Dependencies**: QGIS 3.26+ (for point cloud support), PyQt5 integration
- **Point Cloud Support**: Requires PDAL for LAS/LAZ/COPC format handling

### Running Single Tests
```bash
# No unit tests exist - manual testing required
# Test in QGIS by:
# 1. Installing plugin in QGIS profile
# 2. Loading plugin and testing features
# 3. Checking QGIS Python console for errors
```

## Code Style Guidelines

### File Structure
- `__init__.py`: QGIS plugin entry point with `classFactory(iface)`
- `odm_plugin.py`: Main plugin class extending standard QGIS plugin pattern
- `odm_dialog.py`: Main UI dialog with dock widget interface, point cloud import support
- `odm_connection.py`: Backend connection handling for ODM API
- `metadata.txt`: QGIS plugin metadata
- `resources_rc.py`: Compiled Qt resources
- `AGENTS.md`: This coding guidelines document

### Imports
```python
# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtWidgets import (QDockWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                   QLineEdit, QPushButton, QTabWidget, QWidget,
                                   QGroupBox, QListWidget, QFileDialog, QMessageBox)
from qgis.PyQt.QtCore import QThread, pyqtSignal, QTimer, Qt, QEvent
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer, QgsPointCloudLayer
from .odm_connection import ODMConnection
```

**Import Order:**
1. Standard library imports
2. Third-party imports (QGIS, PyQt)
3. Local module imports

### Naming Conventions

#### Classes
- **CamelCase**: `PhotosDock`, `ODMDialog`, `ConnectionDialog`, `ODMConnection`
- **Suffix patterns**: Dialog classes end with `Dialog`, dock widgets with `Dock`

#### Functions and Methods
- **snake_case**: `create_menu()`, `set_image_paths()`, `load_projects()`
- **Private methods**: No strict convention, but use `_` prefix for internal helpers
- **Event handlers**: `on_scroll()`, `closeEvent()`, `resizeEvent()`

#### Variables
- **snake_case**: `image_paths`, `current_image_index`, `thumbnail_size`
- **Instance variables**: `self.` prefix, descriptive names
- **Constants**: ALL_CAPS if any (rare in this codebase)

### Code Formatting

#### Indentation
- **4 spaces** (standard Python)
- **Line length**: No strict limit, but keep readable (typically <100 chars)

#### Comments
```python
# -*- coding: utf-8 -*-
# Class-level docstrings not used

def create_menu(self):
    """Create the hamburger menu with photo options"""  # Function docstrings used sparingly
    # Inline comments for complex logic
    self.photo_menu = QMenu(self)
```

#### Spacing
```python
# Vertical spacing between logical sections
layout.addWidget(button)

# No extra blank lines within function bodies
def method(self):
    self.value = 1
    self.other = 2
```

### Qt/PyQt Patterns

#### Widget Creation
```python
# Standard pattern
self.button = QPushButton('Text')
self.button.clicked.connect(self.handler)
layout.addWidget(self.button)

# Group boxes without custom styling (default QGIS appearance)
group = QGroupBox('Title')
layout = QVBoxLayout()
group.setLayout(layout)
```

#### Layer Creation
```python
# Raster layers (orthophoto, DSM, DTM)
layer = QgsRasterLayer(file_path, 'Layer Name', 'gdal')

# Point cloud layers (LAS, LAZ, COPC)
layer = QgsPointCloudLayer(file_path, 'Point Cloud', 'pointcloud')

# Vector layers (fallback for older QGIS versions)
layer = QgsVectorLayer(file_path, 'Layer Name', 'ogr')

# Always check validity before adding
if layer.isValid():
    QgsProject.instance().addMapLayer(layer)
```

#### Layout Management
```python
# Main layout pattern
layout = QVBoxLayout()
layout.setContentsMargins(5, 5, 5, 5)  # Compact margins
layout.setSpacing(5)  # Tight spacing
widget.setLayout(layout)

# Scroll areas for long content
scroll = QScrollArea()
scroll.setWidgetResizable(True)
scroll_content = QWidget()
scroll_layout = QVBoxLayout(scroll_content)
scroll.setWidget(scroll_content)

# Tab layout pattern (consistent across all tabs)
tab_layout = QVBoxLayout()
tab_layout.addWidget(scroll)
tab_layout.setContentsMargins(0,0,0,0)  # Zero margins for consistent appearance
self.tab_widget.setLayout(tab_layout)
```

#### Event Handling
```python
# Signal connections
button.clicked.connect(self.handle_click)
list.itemClicked.connect(self.select_item)

# Override methods
def closeEvent(self, event):
    event.ignore()  # Hide instead of close for dock widgets
    self.hide()
```

### Error Handling

#### Exception Patterns
```python
try:
    # Risky operation
    result = self.api_call()
    if not result:
        QMessageBox.warning(self, 'Error', 'Operation failed')
        return
except Exception as e:
    QMessageBox.critical(self, 'Error', f'Unexpected error: {str(e)}')
    print(f"Debug info: {e}")  # Console logging for debugging
```

#### User Feedback
```python
# Success messages
QMessageBox.information(self, 'Success', 'Operation completed')

# Error messages
QMessageBox.critical(self, 'Error', 'Failed to connect to server')

# Progress feedback
from qgis.core import Qgis
self.iface.messageBar().pushMessage('ODM', 'Processing started', Qgis.Info)
```

### Data Persistence

#### QSettings Usage
```python
# Store plugin settings
self.settings = QSettings()
self.settings.setValue('odm_frontend/base_url', url)
self.settings.setValue('odm_frontend/token', token)

# Retrieve settings with defaults
base_url = self.settings.value('odm_frontend/base_url', 'http://localhost:3000')
```

### File Operations

#### Path Handling
```python
# Use os.path for cross-platform compatibility
import os
file_path = os.path.join(directory, filename)
basename = os.path.basename(file_path)

# File dialogs
files, _ = QFileDialog.getOpenFileNames(self, 'Select Images', '', 'Image files (*.jpg *.jpeg *.png)')
```

### UI Design Patterns

#### Dock Widget Structure
```python
class PhotosDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Title')
        self.setMinimumWidth(300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Central widget with layout
        central_widget = QWidget()
        self.setWidget(central_widget)
        layout = QVBoxLayout(central_widget)
```

#### Tab Organization
```python
# Tab widget with scroll areas for compact layout
self.tabs = QTabWidget()
processing_tab = QWidget()
scroll = QScrollArea()
scroll.setWidgetResizable(True)
scroll_content = QWidget()
tab_layout = QVBoxLayout(scroll_content)
scroll.setWidget(scroll_content)
processing_layout = QVBoxLayout()
processing_layout.addWidget(scroll)
processing_tab.setLayout(processing_layout)
self.tabs.addTab(processing_tab, 'Processing')
```

### Network Operations

#### HTTP Requests
```python
import requests

# Connection testing with timeout
try:
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
        return True
except requests.RequestException:
    return False

# File uploads with multipart
files = [('images', open(path, 'rb')) for path in image_paths]
data = {'options': json.dumps(options)}
response = requests.post(url, files=files, data=data)
```

### Point Cloud Operations

#### Point Cloud Import
```python
# Multi-format point cloud import with fallback
point_cloud_paths = [
    'odm_georeferencing/odm_georeferenced_model.laz',  # COPC LAZ (preferred)
    'odm_georeferencing/odm_georeferenced_model.las',  # Standard LAS
    'entwine_pointcloud/ept-data/0-0-0-0.laz',        # Entwine format
    'entwine_pointcloud/pointclouds.laz'              # Web format
]

for pc_path in point_cloud_paths:
    full_path = os.path.join(temp_dir, pc_path)
    if os.path.exists(full_path):
        layer = QgsPointCloudLayer(full_path, f'Point Cloud ({pc_path})', 'pointcloud')
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            break  # Success
```

### Debugging and Logging

#### Console Output
```python
# Debug prints (remove before production)
print(f"Debug: {variable}")

# Status updates in UI
self.status_text.append(f"✓ Operation completed")
self.status_text.append(f"✗ Operation failed")
```

### Plugin Architecture

#### QGIS Integration
```python
# Plugin class structure
class ODMPlugin:
    def __init__(self, iface):
        self.iface = iface  # QGIS interface reference

    def initGui(self):
        # Add toolbar button and menu item
        self.action = QAction(icon, 'ODM Frontend', self.iface.mainWindow())
        self.iface.addPluginToMenu('ODM Frontend', self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        # Clean up on plugin unload
        self.iface.removePluginMenu('ODM Frontend', self.action)
        self.iface.removeToolBarIcon(self.action)
```

### Security Considerations

#### Input Validation
```python
# URL validation
if not url.startswith('http://') and not url.startswith('https://'):
    url = 'http://' + url

# File path validation
if not os.path.exists(path):
    QMessageBox.warning(self, 'Error', 'File not found')
```

#### API Token Handling
```python
# Store tokens securely via QSettings
if self.token:
    headers['Authorization'] = f'Bearer {self.token}'
```

### Performance Guidelines

#### Image Loading
```python
# Lazy loading for thumbnails
self.batch_size = 20  # Load in batches
self.loaded_thumbnails = 0  # Track progress

# Use QPixmap for image display
pixmap = QPixmap(image_path)
scaled_pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
```

#### Memory Management
```python
# Clean up widgets
for i in reversed(range(layout.count())):
    widget = layout.itemAt(i).widget()
    if widget:
        widget.setParent(None)
```

### Testing Guidelines

#### Manual Testing Checklist
- [ ] Plugin loads without errors in QGIS Python console
- [ ] Dock widget appears and functions correctly
- [ ] Connection dialog opens and validates URLs
- [ ] Image selection and thumbnail display works
- [ ] Processing options are applied correctly
- [ ] API calls succeed/fail gracefully
- [ ] Results import to QGIS layers works (orthophoto, DSM, DTM)
- [ ] Point cloud import works (LAS, LAZ, COPC formats)
- [ ] GCP file loading/parsing functions
- [ ] Error messages are user-friendly
- [ ] Tab layouts display without white borders

### Future Enhancements

#### Recent Improvements (Implemented)
- Fixed DSM/DTM import paths to use correct ODM directory structure
- Enhanced point cloud import with multi-format support (LAS/LAZ/COPC)
- Fixed tab layout white border issues with consistent margins
- Improved DTM generation with automatic point cloud classification
- Added proper QGIS point cloud provider usage

#### Potential Improvements
- Implement thumbnail performance optimization (lazy loading, caching)
- Add unit tests with pytest-qgis
- Implement type hints for better IDE support
- Add logging framework instead of print statements
- Create configuration file for plugin settings
- Add automated testing with QGIS testing framework

---

This document should be updated when new patterns or tools are adopted in the codebase.</content>
<parameter name="filePath">C:\Users\vm\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\odm_frontend\AGENTS.md