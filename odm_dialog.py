# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                 QLineEdit, QPushButton, QTabWidget, QWidget,
                                 QGroupBox, QListWidget, QFileDialog, QMessageBox,
                                 QProgressBar, QTextEdit, QCheckBox, QComboBox,
                                 QSpinBox, QDialogButtonBox, QFormLayout)
from qgis.PyQt.QtCore import QThread, pyqtSignal, QTimer
from qgis.core import QgsProject
from .odm_connection import ODMConnection

class ODMDialog(QDialog):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.odm = ODMConnection()
        self.current_project = None
        self.image_paths = []  # Store full image paths
        self.gcp_points = []  # Store GCP points
        self.current_gcp_file = None
        self.gcp_projection = None  # Store GCP coordinate reference system
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('ODM Frontend')
        self.setGeometry(200, 200, 900, 700)  # Larger default size for better readability
        self.setMinimumSize(700, 600)  # Larger minimum size
        self.setMaximumSize(1400, 1000)  # Allow larger maximum

        layout = QVBoxLayout()
        
        # Project controls above tabs
        project_controls_layout = QHBoxLayout()
        
        self.save_project_btn = QPushButton('💾 Save Project')
        self.save_project_btn.clicked.connect(self.save_project)
        self.save_project_btn.setToolTip('Save current configuration to file')
        
        self.open_project_btn = QPushButton('📂 Open Project')
        self.open_project_btn.clicked.connect(self.open_project)
        self.open_project_btn.setToolTip('Load previously saved configuration')
        
        project_controls_layout.addWidget(self.save_project_btn)
        project_controls_layout.addWidget(self.open_project_btn)
        project_controls_layout.addStretch()
        
        layout.addLayout(project_controls_layout)
        
        # Connection settings
        connection_group = QGroupBox('ODM Server Connection')
        connection_layout = QHBoxLayout()
        
        self.url_edit = QLineEdit(self.odm.base_url)
        self.url_edit.setPlaceholderText('http://localhost:3000')
        self.url_edit.setToolTip('ODM/NodeODM server URL (e.g., http://localhost:3000 or http://192.168.1.100:3000)')

        self.token_edit = QLineEdit(self.odm.token)
        self.token_edit.setPlaceholderText('Authentication token (optional)')
        self.token_edit.setToolTip('Authentication token for secured ODM servers (leave empty for no authentication)')

        connect_btn = QPushButton('Test Connection')
        connect_btn.clicked.connect(self.test_connection)
        connect_btn.setToolTip('Test connection to the ODM server to verify it\'s running and accessible')
        
        connection_layout.addWidget(QLabel('URL:'))
        connection_layout.addWidget(self.url_edit)
        connection_layout.addWidget(QLabel('Token:'))
        connection_layout.addWidget(self.token_edit)
        connection_layout.addWidget(connect_btn)
        
        connection_group.setLayout(connection_layout)
        layout.addWidget(connection_group)
        
        # Tab widget
        self.tabs = QTabWidget()
        
        # Processing tab (now first)
        self.processing_tab = QWidget()
        processing_layout = QVBoxLayout()
        
        # Images upload
        images_group = QGroupBox('Images')
        images_layout = QVBoxLayout()
        
        self.images_list = QListWidget()
        self.images_list.itemClicked.connect(self.select_project)
        self.images_list.setToolTip('List of uploaded drone images for processing - click to select')

        add_images_btn = QPushButton('Add Images')
        add_images_btn.clicked.connect(self.add_images)
        add_images_btn.setToolTip('Select and upload drone images (JPEG, PNG, TIFF) for processing')

        clear_images_btn = QPushButton('Clear Images')
        clear_images_btn.clicked.connect(self.clear_images)
        clear_images_btn.setToolTip('Remove all uploaded images from the processing queue')
        
        images_btn_layout = QHBoxLayout()
        images_btn_layout.addWidget(add_images_btn)
        images_btn_layout.addWidget(clear_images_btn)
        
        images_layout.addWidget(self.images_list)
        images_layout.addLayout(images_btn_layout)
        images_group.setLayout(images_layout)
        
        # Processing options
        options_group = QGroupBox('Processing Options')
        options_layout = QVBoxLayout()

        # WebODM Field Presets
        preset_layout = QHBoxLayout()
        preset_label = QLabel('Processing Preset:')
        preset_label.setToolTip('Select from WebODM-compatible processing presets for optimal results')
        preset_layout.addWidget(preset_label)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            'Custom', 'Default', 'High Resolution', 'Fast Orthophoto',
            'Field', 'DSM+DTM', '3D Model'
        ])
        self.preset_combo.setCurrentText('Default')
        self.preset_combo.currentTextChanged.connect(self.apply_preset)
        self.preset_combo.setToolTip('Choose a preset configuration optimized for different use cases')
        preset_layout.addWidget(self.preset_combo)
        preset_layout.addStretch()

        options_layout.addLayout(preset_layout)
        
        # Common options
        feature_extraction_layout = QHBoxLayout()
        feature_label = QLabel('Feature Extraction:')
        feature_label.setToolTip('Algorithm sensitivity for detecting image features')
        feature_extraction_layout.addWidget(feature_label)

        self.feature_extraction_combo = QComboBox()
        self.feature_extraction_combo.addItems(['auto', 'high', 'medium', 'low'])
        self.feature_extraction_combo.setToolTip('Higher settings detect more features but process slower')
        feature_extraction_layout.addWidget(self.feature_extraction_combo)

        camera_lens_layout = QHBoxLayout()
        camera_lens_label = QLabel('Camera Lens:')
        camera_lens_label.setToolTip('Camera lens type for distortion correction')
        camera_lens_layout.addWidget(camera_lens_label)

        self.camera_lens_combo = QComboBox()
        self.camera_lens_combo.addItems(['auto', 'perspective', 'fisheye', 'spherical'])
        self.camera_lens_combo.setToolTip('Select based on your camera lens type')
        camera_lens_layout.addWidget(self.camera_lens_combo)

        # Quality options
        quality_layout = QHBoxLayout()
        quality_label = QLabel('Quality:')
        quality_label.setToolTip('Overall processing quality and resolution')
        quality_layout.addWidget(quality_label)

        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(50)
        self.quality_spin.setToolTip('Higher values = better quality but slower processing (1-100)')
        quality_layout.addWidget(self.quality_spin)
        
        # Additional options
        self.dsm_checkbox = QCheckBox('Generate DSM')
        self.dsm_checkbox.setToolTip('Digital Surface Model: includes terrain + buildings/vegetation')

        self.dtm_checkbox = QCheckBox('Generate DTM')
        self.dtm_checkbox.setToolTip('Digital Terrain Model: bare earth terrain only (no objects)')

        self.orthophoto_checkbox = QCheckBox('Generate Orthophoto')
        self.orthophoto_checkbox.setToolTip('Georeferenced orthophoto mosaic from all images')
        self.orthophoto_checkbox.setChecked(True)
        
        options_layout.addLayout(feature_extraction_layout)
        options_layout.addLayout(camera_lens_layout)
        options_layout.addLayout(quality_layout)
        options_layout.addWidget(self.dsm_checkbox)
        options_layout.addWidget(self.dtm_checkbox)
        options_layout.addWidget(self.orthophoto_checkbox)
        
        options_group.setLayout(options_layout)
        

        
        # Processing controls
        process_btn_layout = QHBoxLayout()
        self.start_task_btn = QPushButton('▶️ Create Task & Start Processing')
        self.start_task_btn.clicked.connect(self.start_task_processing)
        self.start_task_btn.setToolTip('Upload images and start ODM processing with current settings')

        self.stop_task_btn = QPushButton('⏹️ Stop Task')
        self.stop_task_btn.clicked.connect(self.stop_task)
        self.stop_task_btn.setToolTip('Cancel the currently running processing task')
        self.stop_task_btn.setEnabled(False)

        process_btn_layout.addWidget(self.start_task_btn)
        process_btn_layout.addWidget(self.stop_task_btn)
        process_btn_layout.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setToolTip('Real-time processing progress (may take minutes to hours)')

        status_label = QLabel('Status:')
        status_label.setToolTip('Processing status and detailed messages from ODM')

        self.status_text = QTextEdit()
        self.status_text.setMaximumHeight(100)
        self.status_text.setReadOnly(True)
        self.status_text.setToolTip('Live status updates and processing messages')

        processing_layout.addWidget(images_group)
        processing_layout.addWidget(options_group)
        processing_layout.addLayout(process_btn_layout)

        # Add some spacing
        processing_layout.addSpacing(10)

        processing_layout.addWidget(self.progress_bar)
        processing_layout.addWidget(status_label)
        processing_layout.addWidget(self.status_text)
        
        self.processing_tab.setLayout(processing_layout)
        self.tabs.addTab(self.processing_tab, 'Processing')

        # Options tab (moved to 2nd position)
        self.options_tab = QWidget()
        options_tab_layout = QVBoxLayout()

        # Advanced ODM options
        advanced_group = QGroupBox('Advanced Processing Options')
        advanced_layout = QVBoxLayout()

        # Reconstruction options
        recon_layout = QHBoxLayout()
        recon_layout.addWidget(QLabel('Reconstruction:'))
        self.recon_combo = QComboBox()
        self.recon_combo.addItems(['high', 'medium', 'low'])
        self.recon_combo.setCurrentText('high')
        recon_layout.addWidget(self.recon_combo)
        recon_layout.addStretch()

        # Camera parameters
        camera_layout = QHBoxLayout()
        camera_layout.addWidget(QLabel('FOV:'))
        self.fov_spin = QSpinBox()
        self.fov_spin.setRange(1, 180)
        self.fov_spin.setValue(60)
        camera_layout.addWidget(self.fov_spin)
        camera_layout.addWidget(QLabel('degrees'))
        camera_layout.addStretch()

        # Point cloud options
        pointcloud_layout = QHBoxLayout()
        pointcloud_layout.addWidget(QLabel('Point Cloud Density:'))
        self.pc_density_combo = QComboBox()
        self.pc_density_combo.addItems(['high', 'medium', 'low'])
        self.pc_density_combo.setCurrentText('medium')
        pointcloud_layout.addWidget(self.pc_density_combo)
        pointcloud_layout.addStretch()

        advanced_layout.addLayout(recon_layout)
        advanced_layout.addLayout(camera_layout)
        advanced_layout.addLayout(pointcloud_layout)
        advanced_group.setLayout(advanced_layout)

        # Filtering options
        filtering_group = QGroupBox('Point Cloud Filtering')
        filtering_layout = QVBoxLayout()

        # Statistical outlier removal
        outlier_layout = QHBoxLayout()
        outlier_layout.addWidget(QLabel('Statistical Outlier Removal:'))
        self.outlier_checkbox = QCheckBox('Enable')
        self.outlier_checkbox.setChecked(False)
        outlier_layout.addWidget(self.outlier_checkbox)
        outlier_layout.addStretch()

        # Absolute deviation
        deviation_layout = QHBoxLayout()
        deviation_layout.addWidget(QLabel('Standard Deviation:'))
        self.deviation_spin = QSpinBox()
        self.deviation_spin.setRange(1, 50)
        self.deviation_spin.setValue(5)
        deviation_layout.addWidget(self.deviation_spin)
        deviation_layout.addStretch()

        filtering_layout.addLayout(outlier_layout)
        filtering_layout.addLayout(deviation_layout)
        filtering_group.setLayout(filtering_layout)

        # Output options
        output_group = QGroupBox('Output Formats')
        output_layout = QVBoxLayout()

        # Resolution settings
        resolution_layout = QHBoxLayout()
        resolution_layout.addWidget(QLabel('Orthophoto Resolution:'))
        self.resolution_spin = QSpinBox()
        self.resolution_spin.setRange(1, 100)
        self.resolution_spin.setValue(24)
        resolution_layout.addWidget(self.resolution_spin)
        resolution_layout.addWidget(QLabel('px'))
        resolution_layout.addStretch()

        # Tile size
        tile_layout = QHBoxLayout()
        tile_layout.addWidget(QLabel('Tile Size:'))
        self.tile_combo = QComboBox()
        self.tile_combo.addItems(['2048', '4096', '8192'])
        self.tile_combo.setCurrentText('2048')
        tile_layout.addWidget(self.tile_combo)
        tile_layout.addWidget(QLabel('px'))
        tile_layout.addStretch()

        # Additional outputs
        additional_layout = QVBoxLayout()
        self.texture_checkbox = QCheckBox('Generate Textured Mesh')
        self.texture_checkbox.setChecked(True)
        self.video_checkbox = QCheckBox('Generate Video')
        self.video_checkbox.setChecked(False)
        self.report_checkbox = QCheckBox('Generate Processing Report')
        self.report_checkbox.setChecked(True)

        additional_layout.addWidget(self.texture_checkbox)
        additional_layout.addWidget(self.video_checkbox)
        additional_layout.addWidget(self.report_checkbox)

        output_layout.addLayout(resolution_layout)
        output_layout.addLayout(tile_layout)
        output_layout.addLayout(additional_layout)
        output_group.setLayout(output_layout)

        # Performance options
        performance_group = QGroupBox('Performance & Resources')
        performance_layout = QVBoxLayout()

        # Thread count
        threads_layout = QHBoxLayout()
        threads_layout.addWidget(QLabel('Max Threads:'))
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 32)
        self.threads_spin.setValue(0)  # 0 means auto-detect
        threads_layout.addWidget(self.threads_spin)
        threads_layout.addStretch()

        # Memory limit
        memory_layout = QHBoxLayout()
        memory_layout.addWidget(QLabel('Memory Limit (GB):'))
        self.memory_spin = QSpinBox()
        self.memory_spin.setRange(1, 64)
        self.memory_spin.setValue(8)
        memory_layout.addWidget(self.memory_spin)
        memory_layout.addStretch()

        performance_layout.addLayout(threads_layout)
        performance_layout.addLayout(memory_layout)
        performance_group.setLayout(performance_layout)

        # Add all groups to options tab layout
        options_tab_layout.addWidget(advanced_group)
        options_tab_layout.addWidget(filtering_group)
        options_tab_layout.addWidget(output_group)
        options_tab_layout.addWidget(performance_group)
        options_tab_layout.addStretch()

        self.options_tab.setLayout(options_tab_layout)
        self.tabs.addTab(self.options_tab, 'Options')

        # GCP tab (moved to 3rd position)
        self.gcp_tab = QWidget()
        gcp_layout = QVBoxLayout()

        # GCP file management
        gcp_file_group = QGroupBox('GCP File')
        gcp_file_layout = QHBoxLayout()

        self.gcp_file_path = QLineEdit()
        self.gcp_file_path.setPlaceholderText('GCP file path (.txt or .csv)')
        self.gcp_file_path.setReadOnly(True)
        self.gcp_file_path.setToolTip('Path to the currently loaded GCP file')

        self.load_gcp_btn = QPushButton('Load GCP File')
        self.load_gcp_btn.clicked.connect(self.load_gcp_file)
        self.load_gcp_btn.setToolTip('Load existing GCP file (.txt or .csv format)')

        self.save_gcp_btn = QPushButton('Save GCP File')
        self.save_gcp_btn.clicked.connect(self.save_gcp_file)
        self.save_gcp_btn.setToolTip('Save current GCP points to a file')

        gcp_file_layout.addWidget(self.gcp_file_path)
        gcp_file_layout.addWidget(self.load_gcp_btn)
        gcp_file_layout.addWidget(self.save_gcp_btn)

        gcp_file_group.setLayout(gcp_file_layout)

        # GCP point management
        gcp_points_group = QGroupBox('GCP Points')
        gcp_points_layout = QVBoxLayout()

        # GCP list
        self.gcp_list = QListWidget()
        self.gcp_list.itemClicked.connect(self.select_gcp_point)
        self.gcp_list.setToolTip('List of all ground control points with coordinates')

        # GCP controls
        gcp_controls_layout = QHBoxLayout()

        self.add_gcp_btn = QPushButton('Add GCP Point')
        self.add_gcp_btn.clicked.connect(self.add_gcp_point)
        self.add_gcp_btn.setToolTip('Add a new ground control point with coordinates')

        self.edit_gcp_btn = QPushButton('Edit Selected')
        self.edit_gcp_btn.clicked.connect(self.edit_gcp_point)
        self.edit_gcp_btn.setToolTip('Modify the coordinates of the selected GCP point')
        self.edit_gcp_btn.setEnabled(False)

        self.remove_gcp_btn = QPushButton('Remove Selected')
        self.remove_gcp_btn.clicked.connect(self.remove_gcp_point)
        self.remove_gcp_btn.setToolTip('Delete the selected GCP point permanently')
        self.remove_gcp_btn.setEnabled(False)

        gcp_controls_layout.addWidget(self.add_gcp_btn)
        gcp_controls_layout.addWidget(self.edit_gcp_btn)
        gcp_controls_layout.addWidget(self.remove_gcp_btn)
        gcp_controls_layout.addStretch()

        gcp_points_layout.addWidget(self.gcp_list)
        gcp_points_layout.addLayout(gcp_controls_layout)

        gcp_points_group.setLayout(gcp_points_layout)

        # GCP info display
        gcp_info_group = QGroupBox('Point Information')
        gcp_info_layout = QFormLayout()

        self.gcp_id_label = QLabel('ID: -')
        self.gcp_id_label.setToolTip('Unique identifier for this ground control point')

        self.gcp_world_label = QLabel('World: -, -, -')
        self.gcp_world_label.setToolTip('Real-world coordinates (X, Y, Z) in project coordinate system')

        self.gcp_image_label = QLabel('Image: -, -')
        self.gcp_image_label.setToolTip('Pixel coordinates (x, y) in the source image')

        self.gcp_filename_label = QLabel('File: -')
        self.gcp_filename_label.setToolTip('Source image filename containing this GCP point')

        self.gcp_name_label = QLabel('Name: -')
        self.gcp_name_label.setToolTip('Optional name/label for this ground control point')

        gcp_info_layout.addRow('Point ID:', self.gcp_id_label)
        gcp_info_layout.addRow('World Coordinates:', self.gcp_world_label)
        gcp_info_layout.addRow('Image Coordinates:', self.gcp_image_label)
        gcp_info_layout.addRow('Image File:', self.gcp_filename_label)
        gcp_info_layout.addRow('GCP Name:', self.gcp_name_label)

        gcp_info_group.setLayout(gcp_info_layout)

        # Add all groups to GCP layout
        gcp_layout.addWidget(gcp_file_group)
        gcp_layout.addWidget(gcp_points_group)
        gcp_layout.addWidget(gcp_info_group)

        self.gcp_tab.setLayout(gcp_layout)
        self.tabs.addTab(self.gcp_tab, 'GCPs')

        # Tasks tab (moved to 4th position)
        self.tasks_tab = QWidget()
        tasks_layout = QVBoxLayout()

        # Task management buttons
        task_btn_layout = QHBoxLayout()
        self.refresh_tasks_btn = QPushButton('🔄 Refresh Tasks')
        self.refresh_tasks_btn.clicked.connect(self.load_projects)
        self.refresh_tasks_btn.setToolTip('Update the list of tasks from the ODM server')

        self.delete_task_btn = QPushButton('🗑️ Delete Task')
        self.delete_task_btn.clicked.connect(self.delete_task)
        self.delete_task_btn.setToolTip('Permanently delete the selected task and all its data')
        self.delete_task_btn.setEnabled(False)

        task_btn_layout.addWidget(self.refresh_tasks_btn)
        task_btn_layout.addWidget(self.delete_task_btn)
        task_btn_layout.addStretch()

        # Active tasks list
        tasks_list_group = QGroupBox('Active Tasks')
        tasks_list_group.setToolTip('List of all processing tasks - click to select and monitor')
        tasks_list_layout = QVBoxLayout()

        self.projects_list = QListWidget()
        self.projects_list.itemClicked.connect(self.select_project)
        self.projects_list.setMinimumHeight(200)
        self.projects_list.setToolTip('Click on a task to select it for monitoring or deletion')

        tasks_list_layout.addWidget(self.projects_list)
        tasks_list_group.setLayout(tasks_list_layout)

        tasks_layout.addLayout(task_btn_layout)
        tasks_layout.addWidget(tasks_list_group)

        self.tasks_tab.setLayout(tasks_layout)
        self.tabs.addTab(self.tasks_tab, 'Tasks')

        # Results tab (moved to 4th position)
        self.results_tab = QWidget()
        results_layout = QVBoxLayout()

        # Task selection for Results tab
        results_task_group = QGroupBox('Select Task to Monitor')
        results_task_group.setToolTip('Choose which processing task to monitor and download results from')
        results_task_layout = QVBoxLayout()

        self.results_task_combo = QComboBox()
        self.results_task_combo.addItem('No task selected', '')
        self.results_task_combo.currentIndexChanged.connect(self.select_results_task)
        self.results_task_combo.setToolTip('Select a completed task to view status and download results')

        task_label = QLabel('Choose a task to monitor:')
        task_label.setToolTip('Pick a task from the dropdown to monitor its progress and results')

        results_task_layout.addWidget(task_label)
        results_task_layout.addWidget(self.results_task_combo)
        results_task_group.setLayout(results_task_layout)

        results_btn_layout = QHBoxLayout()
        self.refresh_results_btn = QPushButton('Refresh Status')
        self.refresh_results_btn.clicked.connect(self.refresh_status)
        self.refresh_results_btn.setToolTip('Update the status and progress of the selected task')

        self.download_btn = QPushButton('Download Results')
        self.download_btn.clicked.connect(self.download_results)
        self.download_btn.setToolTip('Download all processing results as a ZIP archive')

        self.import_btn = QPushButton('Import to QGIS')
        self.import_btn.clicked.connect(self.import_to_qgis)
        self.import_btn.setToolTip('Import orthophotos, DSMs, and other results directly into QGIS layers')

        results_btn_layout.addWidget(self.refresh_results_btn)
        results_btn_layout.addWidget(self.download_btn)
        results_btn_layout.addWidget(self.import_btn)
        results_btn_layout.addStretch()

        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setToolTip('Detailed status messages and progress information for the selected task')

        results_layout.addWidget(results_task_group)
        results_layout.addLayout(results_btn_layout)
        results_layout.addWidget(self.results_text)

        self.results_tab.setLayout(results_layout)
        self.tabs.addTab(self.results_tab, 'Results')

        layout.addWidget(self.tabs)
        self.setLayout(layout)

        # Load initial projects
        self.load_projects()

        # Apply default preset on startup
        self.apply_preset('Default')
        
    def test_connection(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, 'Connection', 'Please enter a URL for the ODM server.')
            return
            
        if not url.startswith('http://') and not url.startswith('https://'):
            url = 'http://' + url
            self.url_edit.setText(url)
            
        token = self.token_edit.text().strip()
        self.odm.set_credentials(url, token)
        
        if self.odm.test_connection():
            QMessageBox.information(self, 'Connection', f'Successfully connected to ODM server at {url}!')
        else:
            QMessageBox.critical(self, 'Connection', f'Failed to connect to ODM server at {url}.\n\nPlease check:\n1. URL is correct (e.g., http://localhost:3000)\n2. ODM server is running\n3. No firewall blocking the connection')
            
    def load_projects(self):
        tasks = self.odm.get_tasks()
        self.projects_list.clear()

        # Update Results tab combo box
        self.results_task_combo.clear()
        self.results_task_combo.addItem('No task selected', '')

        for task in tasks:
            task_uuid = task.get('uuid', '')
            if task_uuid:  # Only add tasks with valid UUIDs
                # Handle status field (could be dict or direct code)
                status_info = task.get('status', {})
                if isinstance(status_info, dict):
                    status_code = status_info.get('code', 0)
                else:
                    status_code = status_info

                # Convert status codes to readable text
                status_map = {
                    10: 'QUEUED',
                    20: 'RUNNING',
                    30: 'FAILED',
                    40: 'COMPLETED',
                    50: 'CANCELED'
                }
                status_text = status_map.get(status_code, f'UNKNOWN({status_code})')

                task_name = task.get('name', 'Task')
                item_text = f"{task_name} (ID: {task_uuid}) - {status_text}"
                self.projects_list.addItem(item_text)

                # Add to Results combo box
                combo_text = f"{task_name} - {status_text}"
                self.results_task_combo.addItem(combo_text, task_uuid)
            
    def select_project(self, item):
        task_text = item.text()

        # Parse task ID from text format: "Name (ID: uuid) - Status"
        try:
            if 'ID: ' in task_text and ')' in task_text:
                # Split on 'ID: ' and take the part after it
                parts = task_text.split('ID: ')
                if len(parts) > 1:
                    after_id = parts[1]
                    # Split on ')' and take the part before it
                    bracket_parts = after_id.split(')')
                    if len(bracket_parts) > 0:
                        task_id = bracket_parts[0].strip()
                        if task_id and task_id != 'N/A':
                            self.current_project = task_id

                            # Enable delete button when task is selected (only on Tasks tab)
                            self.delete_task_btn.setEnabled(True)

                            # Update button states based on task status
                            self.update_task_buttons()
                            return
                        else:
                            QMessageBox.warning(self, 'Invalid Task', f'Task has no valid ID: {task_text}')
                            return
                    else:
                        QMessageBox.warning(self, 'Parse Error', f'Could not find closing bracket in: {task_text}')
                        return
                else:
                    QMessageBox.warning(self, 'Parse Error', f'Could not find "ID: " in: {task_text}')
                    return
            else:
                # Fallback: try to extract UUID from anywhere in the text
                import re
                uuid_match = re.search(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', task_text)
                if uuid_match:
                    self.current_project = uuid_match.group(0)
                    self.delete_task_btn.setEnabled(True)
                    self.update_task_buttons()
                    return
                else:
                    QMessageBox.warning(self, 'Parse Error', f'Could not extract task ID from: {task_text}')
                    return
        except Exception as e:
            QMessageBox.warning(self, 'Parse Error', f'Failed to parse task text: {task_text}\nError: {str(e)}')
            return

        # Note: No longer auto-switches to Results tab - users can manually navigate
    
    def stop_task(self):
        """Stop the currently selected task"""
        if not self.current_project:
            QMessageBox.warning(self, 'Warning', 'No task selected to stop.')
            return

        reply = QMessageBox.question(
            self, 'Confirm Stop',
            f'Are you sure you want to stop task {self.current_project}?\n\nThis action cannot be undone.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.odm.cancel_task(self.current_project):
                self.status_text.append(f'✓ Task {self.current_project} stopped successfully')
                self.stop_task_btn.setEnabled(False)
                self.start_task_btn.setEnabled(True)
                if hasattr(self, 'status_timer'):
                    self.status_timer.stop()
            else:
                self.status_text.append(f'✗ Failed to stop task {self.current_project}')

    def delete_task(self):
        """Delete the currently selected task"""
        if not self.current_project:
            QMessageBox.warning(self, 'Warning', 'No task selected to delete.')
            return

        reply = QMessageBox.question(
            self, 'Confirm Delete',
            f'Are you sure you want to delete task {self.current_project}?\n\nThis will permanently remove the task and all its data.\nThis action cannot be undone.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.odm.delete_task(self.current_project):
                self.status_text.append(f'✓ Task {self.current_project} deleted successfully')
                old_task = self.current_project
                self.current_project = None
                self.delete_task_btn.setEnabled(False)
                self.stop_task_btn.setEnabled(False)
                self.start_task_btn.setEnabled(len(self.image_paths) > 0)
                if hasattr(self, 'status_timer'):
                    self.status_timer.stop()
                # Refresh the task list (updates both Tasks and Results tabs)
                self.load_projects()
                # Clear results and reset Results combo
                self.results_text.clear()
                self.results_task_combo.setCurrentIndex(0)  # Select "No task selected"
                QMessageBox.information(self, 'Task Deleted', f'Task {old_task} has been deleted.')
            else:
                self.status_text.append(f'✗ Failed to delete task {self.current_project}')
                
    def select_results_task(self):
        """Handle task selection from Results tab combo box"""
        selected_uuid = self.results_task_combo.currentData()
        if selected_uuid:
            self.current_project = selected_uuid
            self.results_text.clear()

            # Update button states based on task status
            self.update_task_buttons()

            # Start monitoring the selected task
            if hasattr(self, 'status_timer'):
                self.start_status_monitoring()
        else:
            # No task selected
            self.current_project = None
            self.results_text.clear()
            if hasattr(self, 'status_timer'):
                self.status_timer.stop()

    def apply_preset(self, preset_name):
        """Apply WebODM preset configuration"""
        if preset_name == 'Custom':
            return  # Don't change anything for custom

        # WebODM Preset Configurations
        presets = {
            'Default': {
                'feature_extraction': 'medium',
                'camera_lens': 'auto',
                'quality': 50,
                'dsm': True,
                'dtm': False,
                'orthophoto': True,
                'reconstruction': 'high',
                'fov': 60,
                'pointcloud_density': 'medium',
                'outlier_removal': False,
                'deviation': 5,
                'resolution': 24,
                'tile_size': '2048',
                'texture_mesh': True,
                'generate_video': False,
                'generate_report': True,
                'threads': 0,
                'memory_limit': 8
            },
            'High Resolution': {
                'feature_extraction': 'high',
                'camera_lens': 'auto',
                'quality': 25,
                'dsm': True,
                'dtm': True,
                'orthophoto': True,
                'reconstruction': 'high',
                'fov': 60,
                'pointcloud_density': 'high',
                'outlier_removal': False,
                'deviation': 5,
                'resolution': 12,
                'tile_size': '2048',
                'texture_mesh': True,
                'generate_video': False,
                'generate_report': True,
                'threads': 0,
                'memory_limit': 8
            },
            'Fast Orthophoto': {
                'feature_extraction': 'low',
                'camera_lens': 'auto',
                'quality': 75,
                'dsm': False,
                'dtm': False,
                'orthophoto': True,
                'reconstruction': 'medium',
                'fov': 60,
                'pointcloud_density': 'low',
                'outlier_removal': False,
                'deviation': 5,
                'resolution': 48,
                'tile_size': '4096',
                'texture_mesh': False,
                'generate_video': False,
                'generate_report': False,
                'threads': 0,
                'memory_limit': 8
            },
            'Field': {
                'feature_extraction': 'high',
                'camera_lens': 'perspective',
                'quality': 30,
                'dsm': True,
                'dtm': False,
                'orthophoto': True,
                'reconstruction': 'high',
                'fov': 60,
                'pointcloud_density': 'medium',
                'outlier_removal': False,
                'deviation': 5,
                'resolution': 16,
                'tile_size': '2048',
                'texture_mesh': False,
                'generate_video': False,
                'generate_report': True,
                'threads': 0,
                'memory_limit': 8
            },
            'DSM+DTM': {
                'feature_extraction': 'medium',
                'camera_lens': 'auto',
                'quality': 50,
                'dsm': True,
                'dtm': True,
                'orthophoto': True,
                'reconstruction': 'high',
                'fov': 60,
                'pointcloud_density': 'medium',
                'outlier_removal': True,
                'deviation': 3,
                'resolution': 24,
                'tile_size': '2048',
                'texture_mesh': True,
                'generate_video': False,
                'generate_report': True,
                'threads': 0,
                'memory_limit': 8
            },
            '3D Model': {
                'feature_extraction': 'high',
                'camera_lens': 'auto',
                'quality': 30,
                'dsm': True,
                'dtm': False,
                'orthophoto': True,
                'reconstruction': 'high',
                'fov': 60,
                'pointcloud_density': 'high',
                'outlier_removal': False,
                'deviation': 5,
                'resolution': 16,
                'tile_size': '2048',
                'texture_mesh': True,
                'generate_video': False,
                'generate_report': True,
                'threads': 0,
                'memory_limit': 12
            }
        }

        if preset_name in presets:
            config = presets[preset_name]

            # Apply Processing tab settings
            self.feature_extraction_combo.setCurrentText(config['feature_extraction'])
            self.camera_lens_combo.setCurrentText(config['camera_lens'])
            self.quality_spin.setValue(config['quality'])
            self.dsm_checkbox.setChecked(config['dsm'])
            self.dtm_checkbox.setChecked(config['dtm'])
            self.orthophoto_checkbox.setChecked(config['orthophoto'])

            # Apply Options tab settings (if they exist)
            if hasattr(self, 'recon_combo'):
                self.recon_combo.setCurrentText(config['reconstruction'])
            if hasattr(self, 'fov_spin'):
                self.fov_spin.setValue(config['fov'])
            if hasattr(self, 'pc_density_combo'):
                self.pc_density_combo.setCurrentText(config['pointcloud_density'])
            if hasattr(self, 'outlier_checkbox'):
                self.outlier_checkbox.setChecked(config['outlier_removal'])
            if hasattr(self, 'deviation_spin'):
                self.deviation_spin.setValue(config['deviation'])
            if hasattr(self, 'resolution_spin'):
                self.resolution_spin.setValue(config['resolution'])
            if hasattr(self, 'tile_combo'):
                self.tile_combo.setCurrentText(config['tile_size'])
            if hasattr(self, 'texture_checkbox'):
                self.texture_checkbox.setChecked(config['texture_mesh'])
            if hasattr(self, 'video_checkbox'):
                self.video_checkbox.setChecked(config['generate_video'])
            if hasattr(self, 'report_checkbox'):
                self.report_checkbox.setChecked(config['generate_report'])
            if hasattr(self, 'threads_spin'):
                self.threads_spin.setValue(config['threads'])
            if hasattr(self, 'memory_spin'):
                self.memory_spin.setValue(config['memory_limit'])

            self.status_text.append(f'✓ Applied {preset_name} preset configuration')

    def update_task_buttons(self):
        """Update button states based on current task status"""
        if not self.current_project:
            self.start_task_btn.setEnabled(len(self.image_paths) > 0)
            self.stop_task_btn.setEnabled(False)
            return

        task_info = self.odm.get_task_info(self.current_project)
        if task_info:
            status_code = task_info.get('status', {}).get('code', 0)
            if status_code == 20:  # RUNNING
                self.start_task_btn.setEnabled(False)
                self.stop_task_btn.setEnabled(True)
            else:
                self.start_task_btn.setEnabled(len(self.image_paths) > 0)
                self.stop_task_btn.setEnabled(False)
            
    def start_status_monitoring(self):
        if hasattr(self, 'status_timer'):
            self.status_timer.stop()
            
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start(3000)  # Check every 3 seconds
        
        # Initial status check
        self.refresh_status()
            
    def add_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, 'Select Images', '', 'Image files (*.jpg *.jpeg *.png *.tif *.tiff)')
        for file in files:
            self.image_paths.append(file)
            self.images_list.addItem(os.path.basename(file))
            
    def clear_images(self):
        self.images_list.clear()
        self.image_paths.clear()
        
    def start_task_processing(self):
        if len(self.image_paths) == 0:
            QMessageBox.warning(self, 'Warning', 'Please add images first on Processing tab.')
            return
            
        from qgis.PyQt.QtWidgets import QInputDialog
        
        name, ok = QInputDialog.getText(self, 'New Task', 'Enter task name:')
        if ok and name:
            # Build comprehensive processing options for NodeODM
            options = {}
            
            # Basic processing options
            if self.dsm_checkbox.isChecked():
                options['dsm'] = True
            if self.dtm_checkbox.isChecked():
                options['dtm'] = True

            # Note: DTM generation is controlled by the Options tab advanced settings
            # The checkbox here only controls import, not generation
            if self.orthophoto_checkbox.isChecked():
                options['orthophoto-resolution'] = str(self.resolution_spin.value())
            
            # Advanced options
            options['reconstruction-quality'] = self.recon_combo.currentText()
            options['camera-lens'] = self.camera_lens_combo.currentText()
            options['point-cloud-quality'] = self.pc_density_combo.currentText()
            options['camera-fov'] = str(self.fov_spin.value())
            
            # Filtering options
            if self.outlier_checkbox.isChecked():
                options['use-3dmesh'] = True  # Enables outlier removal
                options['pc-cleanup'] = True
                options['pc-classify'] = True
                options['pc-filter'] = str(self.deviation_spin.value())
            
            # Output options
            options['mesh-size'] = self.tile_combo.currentText()
            if self.texture_checkbox.isChecked():
                options['textured-mesh'] = True
            if self.report_checkbox.isChecked():
                options['build-overviews'] = True
            
            # Performance options
            if self.threads_spin.value() > 0:
                options['threads'] = str(self.threads_spin.value())
            if self.memory_spin.value() > 0:
                options['max-memory'] = str(self.memory_spin.value())
            
            # Quality mapping
            quality_map = {'auto': 'high', 'high': 'high', 'medium': 'medium', 'low': 'low'}
            options['feature-quality'] = quality_map.get(self.feature_extraction_combo.currentText(), 'medium')
            
            self.status_text.append(f'Creating task "{name}" with {len(self.image_paths)} images...')
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
            
            task = self.odm.create_task(self.image_paths, options, name)
            if task:
                uuid = task.get('uuid')
                QMessageBox.information(self, 'Success', f'Task "{name}" created successfully!\n\nTask ID: {uuid}')
                self.current_project = uuid
                self.load_projects()
                self.start_status_monitoring()
                self.tabs.setCurrentIndex(2)  # Switch to Tasks tab (index 2) to show the new task
                
                # Update button states for new running task
                self.start_task_btn.setEnabled(False)
                self.stop_task_btn.setEnabled(True)
            else:
                QMessageBox.critical(self, 'Error', 'Failed to create task.\n\nCheck that:\n1. NodeODM server is running\n2. Images are valid drone photos\n3. Server has enough resources\n\nSee QGIS Python Console for detailed errors.')
                self.progress_bar.setVisible(False)
            
    def refresh_status(self):
        if not self.current_project:
            return
            
        task_info = self.odm.get_task_info(self.current_project)
        self.results_text.clear()
        
        if task_info:
            # Handle status field (could be dict with code or direct code)
            status_field = task_info.get('status', {})
            if isinstance(status_field, dict):
                status_code = status_field.get('code', 0)
            else:
                status_code = status_field  # Direct integer
                
            progress = task_info.get('progress', 0)
            name = task_info.get('name', 'Unknown')
            processing_time = task_info.get('processingTime', 0)
            
            # Convert status codes to readable text
            status_map = {
                10: 'QUEUED',
                20: 'RUNNING', 
                30: 'FAILED',
                40: 'COMPLETED',
                50: 'CANCELED'
            }
            status_text = status_map.get(status_code, f'UNKNOWN({status_code})')
            
            # Update progress bar
            if status_code == 20:  # RUNNING
                self.progress_bar.setVisible(True)
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(int(progress))  # Convert float to int
            elif status_code in [40, 30, 50]:  # COMPLETED, FAILED, CANCELED
                self.progress_bar.setVisible(False)
            
            # Format processing time
            if processing_time > 0:
                minutes = processing_time // (1000 * 60)
                seconds = (processing_time // 1000) % 60
                time_str = f" ({minutes:02d}:{seconds:02d})"
            else:
                time_str = ""
                
            self.results_text.append(f'{name}: {status_text} ({int(progress)}%){time_str}')
            
            if status_code == 40:  # COMPLETED
                self.status_text.append('✓ Processing completed successfully!')
                if hasattr(self, 'status_timer'):
                    self.status_timer.stop()
            elif status_code == 30:  # FAILED
                self.status_text.append('✗ Processing failed!')
                if hasattr(self, 'status_timer'):
                    self.status_timer.stop()
            
    def download_results(self):
        if not self.current_project:
            return
            
        output_path, _ = QFileDialog.getSaveFileName(self, 'Save Results', '', 'ZIP files (*.zip)')
        if output_path:
            self.status_text.append(f'Downloading results to {output_path}...')
            if self.odm.download_results(self.current_project, output_path):
                self.status_text.append('Download completed!')
            else:
                self.status_text.append('Download failed.')
                
    def save_project(self):
        """Save current project configuration to a JSON file"""
        import json
        
        if len(self.image_paths) == 0:
            QMessageBox.warning(self, 'Warning', 'No images to save. Add images first.')
            return
            
        from qgis.PyQt.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 'Save Project', '', 'ODM Project Files (*.odm);;All Files (*.*)'
        )
        
        if not file_path:
            return
            
        try:
            project_data = {
                'name': getattr(self, 'project_name', 'Untitled Project'),
                'preset': self.preset_combo.currentText(),
                'images': self.image_paths,
                'options': {
                    'feature_extraction': self.feature_extraction_combo.currentText(),
                    'camera_lens': self.camera_lens_combo.currentText(),
                    'quality': self.quality_spin.value(),
                    'dsm': self.dsm_checkbox.isChecked(),
                    'dtm': self.dtm_checkbox.isChecked(),
                    'orthophoto': self.orthophoto_checkbox.isChecked(),
                    'reconstruction': self.recon_combo.currentText(),
                    'fov': self.fov_spin.value(),
                    'pointcloud_density': self.pc_density_combo.currentText(),
                    'outlier_removal': self.outlier_checkbox.isChecked(),
                    'deviation': self.deviation_spin.value(),
                    'resolution': self.resolution_spin.value(),
                    'tile_size': self.tile_combo.currentText(),
                    'texture_mesh': self.texture_checkbox.isChecked(),
                    'generate_video': self.video_checkbox.isChecked(),
                    'generate_report': self.report_checkbox.isChecked(),
                    'threads': self.threads_spin.value(),
                    'memory_limit': self.memory_spin.value()
                },
                'odm_settings': {
                    'base_url': self.odm.base_url,
                    'token': self.odm.token
                }
            }
            
            with open(file_path, 'w') as f:
                json.dump(project_data, f, indent=2)
                
            QMessageBox.information(self, 'Success', f'Project saved to {os.path.basename(file_path)}')
            
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to save project: {str(e)}')
    
    def open_project(self):
        """Load a previously saved project"""
        import json
        
        from qgis.PyQt.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Open Project', '', 'ODM Project Files (*.odm);;All Files (*.*)'
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'r') as f:
                project_data = json.load(f)
                
            # Load images
            self.image_paths = project_data.get('images', [])
            self.images_list.clear()
            for path in self.image_paths:
                if os.path.exists(path):
                    self.images_list.addItem(os.path.basename(path))
                else:
                    self.status_text.append(f'⚠ Image not found: {os.path.basename(path)}')
            
            # Load preset first (this will auto-configure options)
            preset = project_data.get('preset', 'Custom')
            self.preset_combo.setCurrentText(preset)

            # If custom preset, load manual options
            if preset == 'Custom':
                options = project_data.get('options', {})
                self.feature_extraction_combo.setCurrentText(options.get('feature_extraction', 'auto'))
                self.camera_lens_combo.setCurrentText(options.get('camera_lens', 'auto'))
                self.quality_spin.setValue(options.get('quality', 50))
                self.dsm_checkbox.setChecked(options.get('dsm', False))
                self.dtm_checkbox.setChecked(options.get('dtm', False))
                self.orthophoto_checkbox.setChecked(options.get('orthophoto', True))
                self.recon_combo.setCurrentText(options.get('reconstruction', 'high'))
                self.fov_spin.setValue(options.get('fov', 60))
                self.pc_density_combo.setCurrentText(options.get('pointcloud_density', 'medium'))
                self.outlier_checkbox.setChecked(options.get('outlier_removal', False))
                self.deviation_spin.setValue(options.get('deviation', 5))
                self.resolution_spin.setValue(options.get('resolution', 24))
                self.tile_combo.setCurrentText(options.get('tile_size', '2048'))
                self.texture_checkbox.setChecked(options.get('texture_mesh', True))
                self.video_checkbox.setChecked(options.get('generate_video', False))
                self.report_checkbox.setChecked(options.get('generate_report', True))
                self.threads_spin.setValue(options.get('threads', 0))
                self.memory_spin.setValue(options.get('memory_limit', 8))
            
            # Load ODM settings
            odm_settings = project_data.get('odm_settings', {})
            if odm_settings.get('base_url'):
                self.odm.set_credentials(
                    odm_settings['base_url'], 
                    odm_settings.get('token', '')
                )
                self.url_edit.setText(odm_settings['base_url'])
                self.token_edit.setText(odm_settings.get('token', ''))
            
            # Store project name
            self.project_name = project_data.get('name', 'Loaded Project')
            
            QMessageBox.information(self, 'Success', f'Project "{self.project_name}" loaded successfully!')
            
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load project: {str(e)}')
    
    def import_to_qgis(self):
        if not self.current_project:
            QMessageBox.warning(self, 'Warning', 'No task selected. Please select a completed task.')
            return
            
        # Get task info first to check if completed
        task_info = self.odm.get_task_info(self.current_project)
        if not task_info:
            QMessageBox.critical(self, 'Error', 'Could not get task information.')
            return
            
        status_code = task_info.get('status', {}).get('code', 0)
        if status_code != 40:  # Not completed
            QMessageBox.warning(self, 'Warning', 'Task must be completed before importing results.')
            return
            
        # Let user choose what to import
        from qgis.PyQt.QtWidgets import QCheckBox, QDialog, QVBoxLayout, QDialogButtonBox, QLabel
        from qgis.PyQt.QtCore import Qt
        
        class ImportDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle('Import Options')
                self.setModal(True)
                layout = QVBoxLayout()
                
                self.ortho_checkbox = QCheckBox('Import Orthophoto')
                self.ortho_checkbox.setChecked(True)
                
                self.dsm_checkbox = QCheckBox('Import DSM')
                self.dsm_checkbox.setChecked(True)
                
                self.dtm_checkbox = QCheckBox('Import DTM')
                self.dtm_checkbox.setChecked(True)  # Enable by default
                
                self.point_cloud_checkbox = QCheckBox('Import Point Cloud')
                self.point_cloud_checkbox.setChecked(True)
                
                layout.addWidget(QLabel('Select results to import:'))
                layout.addWidget(self.ortho_checkbox)
                layout.addWidget(self.dsm_checkbox)
                layout.addWidget(self.dtm_checkbox)
                layout.addWidget(QLabel('Note: DTM and DSM generation must be enabled in Options tab'))
                layout.addWidget(self.point_cloud_checkbox)
                
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addWidget(buttons)
                
                self.setLayout(layout)
                
            def get_options(self):
                return {
                    'orthophoto': self.ortho_checkbox.isChecked(),
                    'dsm': self.dsm_checkbox.isChecked(),
                    'dtm': self.dtm_checkbox.isChecked(),
                    'point_cloud': self.point_cloud_checkbox.isChecked()
                }
        
        # Show import dialog
        dialog = ImportDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
            
        options = dialog.get_options()
        
        # Download and extract results
        import tempfile
        import os
        import zipfile
        
        try:
            # Create temp directory
            temp_dir = tempfile.mkdtemp()
            zip_path = os.path.join(temp_dir, 'results.zip')
            
            self.status_text.append('Downloading results...')
            if not self.odm.download_results(self.current_project, zip_path):
                QMessageBox.critical(self, 'Error', 'Failed to download results.')
                return
                
            # Extract ZIP
            self.status_text.append('Extracting results...')
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
                
            # Import selected results
            from qgis.core import QgsRasterLayer, QgsVectorLayer, QgsProject
            iface = self.iface
            
            imported_count = 0
            
            # Orthophoto
            if options['orthophoto']:
                ortho_path = os.path.join(temp_dir, 'odm_orthophoto', 'odm_orthophoto.tif')
                if os.path.exists(ortho_path):
                    layer = QgsRasterLayer(ortho_path, 'Orthophoto', 'gdal')
                    if layer.isValid():
                        QgsProject.instance().addMapLayer(layer)
                        imported_count += 1
                        self.status_text.append('✓ Orthophoto imported')
                        
            # DSM
            if options['dsm']:
                dsm_path = os.path.join(temp_dir, 'odm_dsm', 'odm_dsm.tif')
                if os.path.exists(dsm_path):
                    layer = QgsRasterLayer(dsm_path, 'DSM', 'gdal')
                    if layer.isValid():
                        QgsProject.instance().addMapLayer(layer)
                        imported_count += 1
                        self.status_text.append('✓ DSM imported')
                        
            # DTM
            if options['dtm']:
                dtm_path = os.path.join(temp_dir, 'odm_dtm', 'odm_dtm.tif')
                if os.path.exists(dtm_path):
                    layer = QgsRasterLayer(dtm_path, 'DTM', 'gdal')
                    if layer.isValid():
                        QgsProject.instance().addMapLayer(layer)
                        imported_count += 1
                        self.status_text.append('✓ DTM imported')
                    else:
                        self.status_text.append('DTM file exists but could not be loaded as valid layer')
                else:
                    self.status_text.append('DTM file not found - make sure DTM generation was enabled in Options tab during processing')
                    # List available directories for debugging
                    try:
                        dirs = [d for d in os.listdir(temp_dir) if os.path.isdir(os.path.join(temp_dir, d))]
                        self.status_text.append(f'Available result directories: {dirs}')
                    except:
                        self.status_text.append('Could not list result directories')
                        
            # Point Cloud
            if options['point_cloud']:
                las_path = os.path.join(temp_dir, 'odm_georeferenced_model', 'odm_georeferenced_model.las')
                if os.path.exists(las_path):
                    layer = QgsVectorLayer(las_path, 'Point Cloud', 'ogr')
                    if layer.isValid():
                        QgsProject.instance().addMapLayer(layer)
                        imported_count += 1
                        self.status_text.append('✓ Point cloud imported')
                        
            if imported_count > 0:
                iface.mapCanvas().refreshAllLayers()
                QMessageBox.information(self, 'Success', f'Imported {imported_count} layers to QGIS!')
            else:
                QMessageBox.warning(self, 'Warning', 'No valid result files found to import.')
                
            # Cleanup
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Import failed: {str(e)}')
            self.status_text.append(f'✗ Import failed: {str(e)}')

    def _is_projection_line(self, line):
        """Check if a line looks like a projection definition"""
        line = line.strip()
        # Check for common projection formats
        if line.startswith('+proj=') or line.startswith('EPSG:') or 'UTM' in line.upper():
            return True
        return False



    def load_gcp_file(self):
        """Load a GCP file (ODM format only)"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Load GCP File', '', 'GCP Files (*.txt);;All Files (*.*)'
        )

        if not file_path:
            return

        try:
            self.gcp_points = []
            self.gcp_projection = None

            with open(file_path, 'r') as f:
                lines = f.readlines()

            if not lines:
                QMessageBox.warning(self, 'Empty File', 'The selected file is empty.')
                return

            # Check if first line is a projection definition
            first_line = lines[0].strip()
            if self._is_projection_line(first_line):
                # ODM format: first line is projection
                self.gcp_projection = first_line
                data_lines = lines[1:]
                start_line_num = 2
            else:
                # Assume ODM format without explicit projection (default to EPSG:4326)
                self.gcp_projection = 'EPSG:4326'
                data_lines = lines
                start_line_num = 1

            # Parse data lines (whitespace separated)
            for line_num, line in enumerate(data_lines, start_line_num):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # Parse GCP line: geo_x geo_y geo_z im_x im_y filename [gcp_name]
                parts = line.split()
                num_parts = len(parts)

                if num_parts >= 6:
                    # Standard ODM format: geo_x geo_y geo_z im_x im_y filename [gcp_name]
                    try:
                        gcp_point = {
                            'id': len(self.gcp_points) + 1,
                            'world_x': float(parts[0]),  # geo_x (easting/longitude)
                            'world_y': float(parts[1]),  # geo_y (northing/latitude)
                            'world_z': float(parts[2]),  # geo_z (elevation)
                            'image_x': float(parts[3]),  # im_x (pixel x)
                            'image_y': float(parts[4]),  # im_y (pixel y)
                            'filename': parts[5],        # image filename
                            'gcp_name': parts[6] if num_parts > 6 else '',  # optional GCP name
                            'line_num': line_num
                        }
                        self.gcp_points.append(gcp_point)
                    except ValueError as e:
                        QMessageBox.warning(self, 'Parse Error',
                                          f'Error parsing line {line_num}: {line}\n{str(e)}')

                elif num_parts == 4:
                    # Check if this is name-first format: gcp_name geo_x geo_y geo_z
                    try:
                        # Try to parse as numbers for coordinates (fields 2, 3, 4)
                        float(parts[1]), float(parts[2]), float(parts[3])
                        QMessageBox.warning(self, 'Incomplete GCP Data',
                                          f'Line {line_num} is missing required pixel coordinates and filename.\n'
                                          f'Found: {line}\n\n'
                                          'ODM requires FULL GCP data including:\n'
                                          '• Geographic coordinates (X, Y, Z)\n'
                                          '• Pixel coordinates (where the point appears in the image)\n'
                                          '• Image filename (which image contains this point)\n\n'
                                          'Correct format: geo_x geo_y geo_z im_x im_y filename [gcp_name]\n'
                                          'Example: 544256.7 5320919.9 5 3044 2622 IMG_0525.jpg GCP01\n\n'
                                          'To create proper GCPs:\n'
                                          '1. Mark points on your images in an image editor\n'
                                          '2. Record pixel coordinates (x, y) where you clicked\n'
                                          '3. Measure real-world coordinates (GPS/survey)\n'
                                          '4. Include the image filename for each point')
                    except ValueError:
                        QMessageBox.warning(self, 'Parse Error',
                                          f'Invalid GCP format on line {line_num}: {line}\n'
                                          'Expected numeric coordinates in fields 2-4.')
                else:
                    QMessageBox.warning(self, 'Parse Error',
                                      f'Invalid GCP format on line {line_num}: {line}\n'
                                      f'Expected 6+ fields (geo_x geo_y geo_z im_x im_y filename), got {num_parts} fields.')

            if self.gcp_points:
                self.current_gcp_file = file_path
                self.gcp_file_path.setText(file_path)
                self.update_gcp_list()
                projection_info = f" (Projection: {self.gcp_projection})" if self.gcp_projection else ""
                QMessageBox.information(self, 'Success',
                                      f'Loaded {len(self.gcp_points)} GCP points{projection_info}')
            else:
                QMessageBox.warning(self, 'No GCPs Found',
                                  'No valid GCP points were found in the file.')

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load GCP file: {str(e)}')

    def save_gcp_file(self):
        """Save current GCP points to ODM-compatible file"""
        if not self.gcp_points:
            QMessageBox.warning(self, 'Warning', 'No GCP points to save.')
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, 'Save GCP File', '', 'GCP Files (*.txt);;All Files (*.*)'
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w') as f:
                # Write projection header (required for ODM format)
                if hasattr(self, 'gcp_projection') and self.gcp_projection:
                    f.write(f"{self.gcp_projection}\n")
                else:
                    # Default to WGS84 geographic if no projection specified
                    f.write("EPSG:4326\n")

                # Write header comments
                f.write('# GCP file generated by ODM Frontend\n')
                f.write('# Compatible with OpenDroneMap/WebODM\n')
                f.write('# Format: geo_x geo_y geo_z im_x im_y filename [gcp_name]\n')
                f.write('# Fields separated by tabs\n')

                # Write GCP data (tab-separated)
                for gcp in self.gcp_points:
                    fields = [
                        f"{gcp['world_x']}",    # geo_x
                        f"{gcp['world_y']}",    # geo_y
                        f"{gcp['world_z']}",    # geo_z
                        f"{gcp['image_x']}",    # im_x
                        f"{gcp['image_y']}",    # im_y
                        gcp['filename']         # image filename
                    ]

                    # Add optional GCP name if present
                    if gcp.get('gcp_name'):
                        fields.append(gcp['gcp_name'])

                    # Join with tabs and write line
                    line = '\t'.join(fields) + '\n'
                    f.write(line)

            self.current_gcp_file = file_path
            self.gcp_file_path.setText(file_path)

            projection_info = f" (Projection: {self.gcp_projection or 'EPSG:4326'})"
            QMessageBox.information(self, 'Success',
                                  f'Saved {len(self.gcp_points)} GCP points to {os.path.basename(file_path)}\n'
                                  f'Format: ODM-compatible (tab-separated){projection_info}')

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to save GCP file: {str(e)}')

    def update_gcp_list(self):
        """Update the GCP points list display"""
        self.gcp_list.clear()
        for gcp in self.gcp_points:
            gcp_name = f" ({gcp['gcp_name']})" if gcp.get('gcp_name') else ""
            item_text = f"GCP {gcp['id']}{gcp_name}: ({gcp['world_x']:.2f}, {gcp['world_y']:.2f}, {gcp['world_z']:.2f}) → {gcp['filename']}"
            self.gcp_list.addItem(item_text)

    def select_gcp_point(self, item):
        """Handle GCP point selection"""
        try:
            # Extract GCP ID from item text
            text = item.text()
            if text.startswith('GCP '):
                gcp_id = int(text.split()[1].rstrip(':'))
                gcp = next((g for g in self.gcp_points if g['id'] == gcp_id), None)
                if gcp:
                    self.gcp_id_label.setText(f"ID: {gcp['id']}")
                    self.gcp_world_label.setText(f"World: {gcp['world_x']:.2f}, {gcp['world_y']:.2f}, {gcp['world_z']:.2f}")
                    self.gcp_image_label.setText(f"Image: {gcp['image_x']:.1f}, {gcp['image_y']:.1f}")
                    self.gcp_filename_label.setText(f"File: {gcp['filename']}")
                    self.gcp_name_label.setText(f"Name: {gcp.get('gcp_name', '-')}")

                    self.edit_gcp_btn.setEnabled(True)
                    self.remove_gcp_btn.setEnabled(True)
                else:
                    self.clear_gcp_info()
        except Exception as e:
            self.clear_gcp_info()
            print(f"Error selecting GCP: {e}")

    def clear_gcp_info(self):
        """Clear GCP information display"""
        self.gcp_id_label.setText('ID: -')
        self.gcp_world_label.setText('World: -, -, -')
        self.gcp_image_label.setText('Image: -, -')
        self.gcp_filename_label.setText('File: -')
        self.gcp_name_label.setText('Name: -')
        self.edit_gcp_btn.setEnabled(False)
        self.remove_gcp_btn.setEnabled(False)

    def add_gcp_point(self):
        """Add a new GCP point"""
        from qgis.PyQt.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox

        class GCPDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle('Add GCP Point')
                self.setModal(True)

                layout = QFormLayout()

                self.world_x = QDoubleSpinBox()
                self.world_x.setRange(-1000000, 1000000)
                self.world_x.setDecimals(2)

                self.world_y = QDoubleSpinBox()
                self.world_y.setRange(-1000000, 1000000)
                self.world_y.setDecimals(2)

                self.world_z = QDoubleSpinBox()
                self.world_z.setRange(-10000, 10000)
                self.world_z.setDecimals(2)

                self.image_x = QDoubleSpinBox()
                self.image_x.setRange(0, 10000)
                self.image_x.setDecimals(1)

                self.image_y = QDoubleSpinBox()
                self.image_y.setRange(0, 10000)
                self.image_y.setDecimals(1)

                self.filename = QLineEdit()
                self.filename.setPlaceholderText('Image filename (optional)')

                layout.addRow('World X:', self.world_x)
                layout.addRow('World Y:', self.world_y)
                layout.addRow('World Z:', self.world_z)
                layout.addRow('Image X:', self.image_x)
                layout.addRow('Image Y:', self.image_y)
                layout.addRow('Image File:', self.filename)

                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addRow(buttons)

                self.setLayout(layout)

            def get_values(self):
                return {
                    'world_x': self.world_x.value(),
                    'world_y': self.world_y.value(),
                    'world_z': self.world_z.value(),
                    'image_x': self.image_x.value(),
                    'image_y': self.image_y.value(),
                    'filename': self.filename.text().strip()
                }

        dialog = GCPDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            values = dialog.get_values()
            gcp_point = {
                'id': len(self.gcp_points) + 1,
                'world_x': values['world_x'],
                'world_y': values['world_y'],
                'world_z': values['world_z'],
                'image_x': values['image_x'],
                'image_y': values['image_y'],
                'filename': values['filename'],
                'line_num': 0
            }
            self.gcp_points.append(gcp_point)
            self.update_gcp_list()
            QMessageBox.information(self, 'Success', f'GCP point {gcp_point["id"]} added')

    def edit_gcp_point(self):
        """Edit the selected GCP point"""
        # Find selected GCP
        current_item = self.gcp_list.currentItem()
        if not current_item:
            return

        try:
            text = current_item.text()
            gcp_id = int(text.split()[1].rstrip(':'))
            gcp = next((g for g in self.gcp_points if g['id'] == gcp_id), None)
            if not gcp:
                return

            from qgis.PyQt.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox

            class GCPDialog(QDialog):
                def __init__(self, gcp_data, parent=None):
                    super().__init__(parent)
                    self.setWindowTitle('Edit GCP Point')
                    self.setModal(True)

                    layout = QFormLayout()

                    self.world_x = QDoubleSpinBox()
                    self.world_x.setRange(-1000000, 1000000)
                    self.world_x.setDecimals(2)
                    self.world_x.setValue(gcp_data['world_x'])

                    self.world_y = QDoubleSpinBox()
                    self.world_y.setRange(-1000000, 1000000)
                    self.world_y.setDecimals(2)
                    self.world_y.setValue(gcp_data['world_y'])

                    self.world_z = QDoubleSpinBox()
                    self.world_z.setRange(-10000, 10000)
                    self.world_z.setDecimals(2)
                    self.world_z.setValue(gcp_data['world_z'])

                    self.image_x = QDoubleSpinBox()
                    self.image_x.setRange(0, 10000)
                    self.image_x.setDecimals(1)
                    self.image_x.setValue(gcp_data['image_x'])

                    self.image_y = QDoubleSpinBox()
                    self.image_y.setRange(0, 10000)
                    self.image_y.setDecimals(1)
                    self.image_y.setValue(gcp_data['image_y'])

                    self.filename = QLineEdit(gcp_data['filename'])

                    layout.addRow('World X:', self.world_x)
                    layout.addRow('World Y:', self.world_y)
                    layout.addRow('World Z:', self.world_z)
                    layout.addRow('Image X:', self.image_x)
                    layout.addRow('Image Y:', self.image_y)
                    layout.addRow('Image File:', self.filename)

                    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                    buttons.accepted.connect(self.accept)
                    buttons.rejected.connect(self.reject)
                    layout.addRow(buttons)

                    self.setLayout(layout)

                def get_values(self):
                    return {
                        'world_x': self.world_x.value(),
                        'world_y': self.world_y.value(),
                        'world_z': self.world_z.value(),
                        'image_x': self.image_x.value(),
                        'image_y': self.image_y.value(),
                        'filename': self.filename.text().strip()
                    }

            dialog = GCPDialog(gcp, self)
            if dialog.exec_() == QDialog.Accepted:
                values = dialog.get_values()
                gcp.update(values)
                self.update_gcp_list()
                self.select_gcp_point(current_item)  # Refresh info display
                QMessageBox.information(self, 'Success', f'GCP point {gcp["id"]} updated')

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to edit GCP point: {str(e)}')

    def remove_gcp_point(self):
        """Remove the selected GCP point"""
        current_item = self.gcp_list.currentItem()
        if not current_item:
            return

        try:
            text = current_item.text()
            gcp_id = int(text.split()[1].rstrip(':'))

            reply = QMessageBox.question(
                self, 'Confirm Delete',
                f'Are you sure you want to delete GCP point {gcp_id}?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self.gcp_points = [g for g in self.gcp_points if g['id'] != gcp_id]
                # Renumber remaining GCPs
                for i, gcp in enumerate(self.gcp_points, 1):
                    gcp['id'] = i
                self.update_gcp_list()
                self.clear_gcp_info()
                QMessageBox.information(self, 'Success', 'GCP point deleted')

        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to delete GCP point: {str(e)}')