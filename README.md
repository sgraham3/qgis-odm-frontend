# ODM Frontend - QGIS Plugin

A comprehensive QGIS plugin that provides a user-friendly interface to OpenDroneMap (ODM) processing capabilities, enabling seamless drone image processing workflows directly within QGIS.

## 🎯 Purpose

The ODM Frontend plugin bridges the gap between QGIS and OpenDroneMap/NodeODM servers, offering drone operators and GIS professionals an intuitive way to:

- **Process drone imagery** into orthophotos, digital elevation models, and 3D models
- **Manage processing tasks** with real-time monitoring and status updates
- **Import results** directly into QGIS layers with proper CRS support
- **Handle ground control points** for accurate georeferencing
- **Configure processing presets** optimized for different use cases

## ✨ Key Features

### 🖼️ Image Processing
- Drag-and-drop interface for uploading drone images (JPEG, PNG, TIFF)
- Support for multiple image formats and batch processing
- Real-time processing progress monitoring
- Automatic result download and QGIS import

### 🎛️ Processing Options
- **6 WebODM-Compatible Presets**: Default, High Resolution, Fast Orthophoto, Field, DSM+DTM, 3D Model
- **Advanced Options**: Reconstruction quality, camera lens correction, point cloud density
- **Output Formats**: Orthophotos, DSM, DTM, textured meshes, point clouds
- **Performance Tuning**: Thread count, memory limits, tile sizes

### 📍 Ground Control Points (GCPs)
- Complete GCP management interface
- Load/save GCP files in ODM-compatible format
- Real-time coordinate validation
- Support for multiple coordinate systems (EPSG, PROJ, UTM)

### 📊 Task Management
- Monitor active and completed processing tasks
- Task filtering and selection
- Real-time status updates and progress bars
- Task cancellation and deletion capabilities

### 🔗 QGIS Integration
- Direct import of orthophotos, DSMs, DTMs, and point clouds
- Automatic CRS assignment and layer management
- Seamless workflow integration with existing QGIS projects

## 🛠️ Installation

### Prerequisites
- **QGIS**: Version 3.0 or later
- **OpenDroneMap Server**: NodeODM or WebODM instance running locally or remotely
- **Python Dependencies**: Included with QGIS installation

### Plugin Installation
1. **Download the Plugin**
   ```bash
   # Clone or download the odm_frontend directory
   git clone https://github.com/your-repo/odm-frontend.git
   ```

2. **Install in QGIS**
   - Copy the `odm_frontend` folder to your QGIS plugins directory:
     - Windows: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
     - Linux/Mac: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - Restart QGIS
   - Enable the plugin in `Plugins → Manage and Install Plugins`

3. **Alternative: ZIP Installation**
   - Create a ZIP file of the `odm_frontend` folder
   - Install via `Plugins → Manage and Install Plugins → Install from ZIP`

## 🚀 Usage

### Initial Setup
1. **Launch the Plugin**
   - Open QGIS and click the ODM Frontend icon in the toolbar
   - Or access via `Plugins → ODM Frontend → ODM Frontend`

2. **Configure Server Connection**
   - Enter your ODM server URL (e.g., `http://localhost:3000` for local NodeODM)
   - Add authentication token if required
   - Click "Test Connection" to verify

### Processing Workflow

#### Step 1: Prepare Images
- Switch to the **"Processing"** tab
- Click **"Add Images"** to select your drone photos
- Images will appear in the list with filenames

#### Step 2: Configure Processing
- Choose a **Processing Preset** from the dropdown (recommended: "Default")
- Adjust advanced options if needed:
  - Quality settings
  - Output formats (DSM, DTM, Orthophoto)
  - Camera parameters

#### Step 3: Add Ground Control Points (Optional)
- Switch to the **"GCPs"** tab
- Load existing GCP file or create new points
- GCP format: `geo_x geo_y geo_z im_x im_y image_name [gcp_name]`
- Example:
  ```
  EPSG:32610
  544256.7 5320919.9 5 3044 2622 IMG_0525.jpg GCP01
  ```

#### Step 4: Start Processing
- Click **"Create Task & Start Processing"**
- Enter a task name when prompted
- Monitor progress in the status area

#### Step 5: Monitor and Download
- Switch to the **"Tasks"** tab to view processing status
- Use the **"Results"** tab for detailed monitoring
- Click **"Download Results"** when complete
- Use **"Import to QGIS"** for automatic layer creation

### Task Management
- **View Tasks**: Browse all processing tasks on the server
- **Monitor Progress**: Real-time status updates and progress bars
- **Cancel Tasks**: Stop running tasks if needed
- **Delete Tasks**: Remove completed or unwanted tasks

## 📋 GCP File Format

The plugin supports the standard OpenDroneMap GCP format:

```
[CRS or PROJ definition]
geo_x geo_y geo_z im_x im_y image_name [gcp_name] [extra1] [extra2]
```

### Examples

**With EPSG Code:**
```
EPSG:32610
544256.7 5320919.9 5 3044 2622 IMG_0525.jpg
544157.7 5320899.2 5 4193 1552 IMG_0585.jpg
```

**With PROJ String:**
```
+proj=utm +zone=10 +ellps=WGS84 +datum=WGS84 +units=m +no_defs
544256.7 5320919.9 5 3044 2622 IMG_0525.jpg
544157.7 5320899.2 5 4193 1552 IMG_0585.jpg
```

### Field Descriptions
- `geo_x, geo_y, geo_z`: Geographic coordinates (easting, northing, elevation)
- `im_x, im_y`: Pixel coordinates in the source image
- `image_name`: Source image filename
- `gcp_name`: Optional label/name for the ground control point

## ⚙️ Configuration Options

### Processing Presets
- **Default**: Balanced processing for most use cases
- **High Resolution**: Maximum quality, slower processing
- **Fast Orthophoto**: Quick orthophoto generation
- **Field**: Optimized for agricultural/field surveys
- **DSM+DTM**: Digital surface and terrain models
- **3D Model**: High-quality textured 3D models

### Advanced Settings
- **Reconstruction Quality**: high/medium/low processing detail
- **Camera Lens**: auto/perspective/fisheye/spherical correction
- **Point Cloud Density**: high/medium/low detail level
- **Resolution**: Output pixel resolution
- **Threads**: CPU core utilization
- **Memory**: RAM allocation limits

## 🐛 Troubleshooting

### Connection Issues
- **Cannot connect to server**: Verify ODM server is running and URL is correct
- **Authentication failed**: Check token is valid for secured servers
- **Firewall blocking**: Ensure port 3000 (default) is accessible

### Processing Issues
- **Task fails immediately**: Check images are valid drone photos
- **Out of memory**: Reduce quality settings or increase memory limit
- **Poor results**: Add ground control points for better accuracy

### GCP Issues
- **Invalid format error**: Ensure file follows ODM format with pixel coordinates
- **Coordinate system mismatch**: Verify CRS matches your project
- **Missing pixel coords**: Use image editor to identify exact pixel locations

### Import Issues
- **Layers not appearing**: Check QGIS coordinate system matches output
- **Corrupt files**: Redownload results from ODM server
- **Memory issues**: Close other QGIS layers before importing

## 📚 Additional Resources

- [OpenDroneMap Documentation](https://docs.opendronemap.org/)
- [WebODM User Guide](https://docs.webodm.net/)
- [QGIS Documentation](https://docs.qgis.org/)
- [Community Forum](https://community.opendronemap.org/)

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

### Development Setup
```bash
# Clone the repository
git clone https://github.com/your-repo/odm-frontend.git
cd odm-frontend

# Install in development mode
# Copy odm_frontend folder to QGIS plugins directory
# Restart QGIS and enable plugin for testing
```

## 📄 License

This project is licensed under the GNU General Public License v3.0 - see the LICENSE file for details.

## 🙏 Acknowledgments

- OpenDroneMap project for the processing engine
- QGIS project for the GIS platform
- WebODM for inspiration and compatibility
- The drone mapping community for feedback and testing

---

**ODM Frontend** - Bringing professional drone processing to QGIS users worldwide.