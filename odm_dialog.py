# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtWidgets import (QDockWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                  QLineEdit, QPushButton, QTabWidget, QWidget,
                                  QGroupBox, QListWidget, QFileDialog, QMessageBox,
                                  QTextEdit, QCheckBox, QComboBox,
                                  QSpinBox, QDialogButtonBox, QFormLayout, QSizePolicy,
                                  QGridLayout, QScrollArea, QMenu, QAction, QDialog, QSizePolicy, QFrame)
from qgis.PyQt.QtCore import QThread, pyqtSignal, QTimer, Qt, QEvent
from qgis.core import QgsProject
from .odm_connection import ODMConnection


class PhotosDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_dialog = parent  # Reference to ODMDialog
        self.image_paths = []
        self.current_image_index = -1
        self.thumbnail_size = 120  # Smaller base thumbnail size for better loading
        self.loaded_thumbnails = 0  # Track loaded thumbnails for progress
        self.batch_size = 20  # Load thumbnails in batches
        self.loading_dialog = None
        self.images_first_loaded = False  # Track if images have been loaded before
        self.setObjectName('odm_photos_dock')
        self.setWindowTitle('ODM Photos')
        self.setMinimumWidth(300)
        self.setMinimumHeight(250)
        # Allow free resizing
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Create central widget
        central_widget = QWidget()
        self.setWidget(central_widget)

        # Main layout
        layout = QVBoxLayout(central_widget)
        layout.setSizeConstraint(QVBoxLayout.SetNoConstraint)

        # Compact header with hamburger menu
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel('Photos'))
        header_layout.addStretch()

        # Hamburger menu button
        self.menu_btn = QPushButton('☰')
        self.menu_btn.setFixedWidth(30)
        self.menu_btn.setFixedHeight(25)
        self.menu_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #007bff;
                border: none;
                font-size: 16px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                color: #0056b3;
                background-color: #f0f0f0;
            }
        """)
        self.menu_btn.setToolTip('Photo options')
        self.create_menu()
        header_layout.addWidget(self.menu_btn)

        layout.addLayout(header_layout)

        # Image display area with scroll area (expanded space)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.image_container = QWidget()
        self.image_layout = QGridLayout(self.image_container)
        self.image_layout.setAlignment(Qt.AlignTop)
        self.image_layout.setSpacing(8)
        self.image_layout.setContentsMargins(8, 8, 8, 8)

        # Ensure container can expand
        self.image_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.scroll_area.setWidget(self.image_container)
        self.scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Connect scroll event to load more images when nearing bottom
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll)
        layout.addWidget(self.scroll_area)



    def create_menu(self):
        """Create the hamburger menu with photo options"""
        self.photo_menu = QMenu(self)

        # Rotate left
        rotate_left_action = QAction('↺ Rotate Left', self)
        rotate_left_action.triggered.connect(self.rotate_left)
        self.photo_menu.addAction(rotate_left_action)

        # Rotate right
        rotate_right_action = QAction('↻ Rotate Right', self)
        rotate_right_action.triggered.connect(self.rotate_right)
        self.photo_menu.addAction(rotate_right_action)

        self.photo_menu.addSeparator()

        # Remove selected
        remove_action = QAction('🗑️ Remove Selected', self)
        remove_action.triggered.connect(self.remove_image)
        self.photo_menu.addAction(remove_action)

        self.photo_menu.addSeparator()

        # Fit to window
        fit_action = QAction('🔍 Fit to Window', self)
        fit_action.triggered.connect(self.fit_to_window)
        self.photo_menu.addAction(fit_action)

        # Connect menu to button
        self.menu_btn.setMenu(self.photo_menu)

        # Initially disable selection-dependent actions
        self.enable_menu_actions(False)

    def enable_menu_actions(self, enabled):
        """Enable/disable menu actions based on selection"""
        for action in self.photo_menu.actions():
            if action.text() in ['↺ Rotate Left', '↻ Rotate Right', '🗑️ Remove Selected']:
                action.setEnabled(enabled)

    def set_image_paths(self, image_paths):
        """Set the list of image paths to display with lazy loading"""
        # Check if images actually changed
        images_changed = self.image_paths != image_paths
        self.image_paths = image_paths.copy()

        # Only show loading dialog on first significant load of images
        should_show_loading = len(self.image_paths) > 20 and not self.images_first_loaded
        if should_show_loading:
            self.show_loading_dialog()
            self.images_first_loaded = True

        # Only refresh display if images changed or nothing is loaded yet
        if images_changed or self.loaded_thumbnails == 0:
            self.refresh_image_display()

        if self.image_paths:
            self.current_image_index = -1  # No initial selection
            self.enable_menu_actions(False)

    def show_loading_dialog(self):
        """Show a loading dialog for image processing"""
        from qgis.PyQt.QtWidgets import QProgressDialog
        self.loading_dialog = QProgressDialog("Loading image thumbnails...", "Cancel", 0, 100, self)
        self.loading_dialog.setWindowModality(Qt.WindowModal)
        self.loading_dialog.setMinimumDuration(500)  # Show after 500ms
        self.loading_dialog.setValue(5)  # Initial progress
        self.loading_dialog.show()  # Disable menu actions until selection

    def refresh_image_display(self):
        """Refresh the image thumbnails display with lazy loading"""
        # Clear existing images
        for i in reversed(range(self.image_layout.count())):
            widget = self.image_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        self.loaded_thumbnails = 0

        # Reset first load flag if no images
        if not self.image_paths:
            self.images_first_loaded = False

        # If no images, nothing to do
        if not self.image_paths:
            return

        # Calculate columns based on dock width and thumbnail size
        dock_width = self.width()
        margin_space = 60  # Account for margins and scrollbars
        available_width = max(200, dock_width - margin_space)
        self.cols = max(2, available_width // (self.thumbnail_size + 20))  # Minimum 2 columns, 20px spacing
        print(f"Dock width: {dock_width}, Available: {available_width}, Thumbnail size: {self.thumbnail_size}, Columns: {self.cols}")  # Debug

        # Load first batch immediately
        self.load_next_batch()

    def load_next_batch(self):
        """Load the next batch of image thumbnails"""
        if self.loaded_thumbnails >= len(self.image_paths):
            # All images loaded, close loading dialog
            if hasattr(self, 'loading_dialog') and self.loading_dialog:
                self.loading_dialog.setValue(100)
                self.loading_dialog.close()
            return

        # For now, load all images at once to test basic functionality
        # Calculate batch range
        start_idx = self.loaded_thumbnails
        end_idx = len(self.image_paths)  # Load all remaining

        # Load this batch
        for i in range(start_idx, end_idx):
            try:
                # Create thumbnail widget
                thumbnail_widget = self.create_image_thumbnail(self.image_paths[i], i)
                row = i // self.cols
                col = i % self.cols
                self.image_layout.addWidget(thumbnail_widget, row, col)
                print(f"Added image {i} at grid position ({row}, {col})")  # Debug
            except Exception as e:
                print(f"Error loading image {self.image_paths[i]}: {e}")

        self.loaded_thumbnails = end_idx

        # Update progress dialog
        if hasattr(self, 'loading_dialog') and self.loading_dialog:
            self.loading_dialog.setValue(100)
            self.loading_dialog.close()  # Load next batch after 50ms

    def create_image_thumbnail(self, image_path, index):
        """Create a thumbnail widget for an image"""
        from qgis.PyQt.QtGui import QPixmap, QImage

        # Create a simple widget with basic styling
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # Load and scale image
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            # If image fails to load, show a placeholder
            image_label = QLabel("Image Load Error")
            image_label.setAlignment(Qt.AlignCenter)
            image_label.setStyleSheet("color: red; font-size: 10px;")
        else:
            # Scale to current thumbnail size
            scaled_pixmap = pixmap.scaled(self.thumbnail_size, self.thumbnail_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            image_label = QLabel()
            image_label.setPixmap(scaled_pixmap)
            image_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(image_label)

        # Filename label
        filename_label = QLabel(os.path.basename(image_path))
        filename_label.setAlignment(Qt.AlignCenter)
        filename_label.setStyleSheet("font-size: 8px; color: #666;")
        filename_label.setWordWrap(True)
        layout.addWidget(filename_label)

        # Make clickable with minimal styling
        widget.mousePressEvent = lambda event, idx=index: self.select_image(idx)
        widget.setStyleSheet("""
            QWidget {
                border: 1px solid transparent;
                background-color: transparent;
                margin: 3px;
            }
            QWidget:hover {
                border: 1px solid #0078d4;
                background-color: rgba(0, 120, 212, 0.05);
            }
        """)

        return widget

    def select_image(self, index):
        """Select an image for operations"""
        self.current_image_index = index

        # Enable/disable menu actions
        self.enable_menu_actions(index >= 0)

        # Highlight selected image
        for i in range(self.image_layout.count()):
            widget = self.image_layout.itemAt(i).widget()
            if i == index:
                widget.setStyleSheet("""
                    QWidget {
                        border: 2px solid #0078d4;
                        background-color: rgba(0, 120, 212, 0.1);
                        margin: 3px;
                    }
                """)
            else:
                widget.setStyleSheet("""
                    QWidget {
                        border: 1px solid transparent;
                        background-color: transparent;
                        margin: 3px;
                    }
                    QWidget:hover {
                        border: 1px solid #0078d4;
                        background-color: rgba(0, 120, 212, 0.05);
                    }
                """)



    def rotate_left(self):
        """Rotate current image left (90 degrees counter-clockwise)"""
        if 0 <= self.current_image_index < len(self.image_paths):
            self._rotate_image(-90)

    def rotate_right(self):
        """Rotate current image right (90 degrees clockwise)"""
        if 0 <= self.current_image_index < len(self.image_paths):
            self._rotate_image(90)

    def _rotate_image(self, angle):
        """Rotate the current image by the given angle"""
        from qgis.PyQt.QtGui import QPixmap, QImage, QTransform

        image_path = self.image_paths[self.current_image_index]
        
        try:
            # Load the image
            image = QImage(image_path)
            if image.isNull():
                QMessageBox.warning(self, 'Error', f'Failed to load image: {os.path.basename(image_path)}')
                return

            # Create transform and rotate
            transform = QTransform()
            transform.rotate(angle)
            rotated_image = image.transformed(transform, Qt.SmoothTransformation)

            # Save the rotated image back to the same file
            if rotated_image.save(image_path):
                # Refresh the thumbnail display
                self.refresh_image_display()
                # Re-select the image
                if self.current_image_index < self.image_layout.count():
                    self.select_image(self.current_image_index)
            else:
                QMessageBox.warning(self, 'Error', f'Failed to save rotated image: {os.path.basename(image_path)}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to rotate image: {str(e)}')

    def remove_image(self):
        """Remove current image from project"""
        if 0 <= self.current_image_index < len(self.image_paths):
            image_path = self.image_paths[self.current_image_index]
            reply = QMessageBox.question(
                self, 'Remove Image',
                f'Are you sure you want to remove "{os.path.basename(image_path)}" from the project?',
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                # Remove from list
                self.image_paths.pop(self.current_image_index)
                # Notify parent dialog to update
                if self.parent_dialog:
                    self.parent_dialog.image_paths = self.image_paths.copy()
                    self.parent_dialog.update_images_display()
                # Refresh display
                self.refresh_image_display()
                # Update selection
                if self.image_paths:
                    if self.current_image_index >= len(self.image_paths):
                        self.current_image_index = len(self.image_paths) - 1
                    self.select_image(self.current_image_index)
                else:
                    self.current_image_index = -1

    def fit_to_window(self):
        """Fit images to window width"""
        # TODO: Implement fit to window
        QMessageBox.information(self, 'Fit', 'Fit to window functionality would be implemented here')

    def on_scroll(self, value):
        """Handle scroll events to load more images when nearing bottom"""
        scrollbar = self.scroll_area.verticalScrollBar()
        max_value = scrollbar.maximum()
        current_value = scrollbar.value()

        # Load more images when user scrolls to within 100px of bottom
        if max_value - current_value < 100 and self.loaded_thumbnails < len(self.image_paths):
            self.load_next_batch()

    def resizeEvent(self, event):
        """Handle resize events to update thumbnail sizes and grid layout"""
        super().resizeEvent(event)

        # Only refresh if we have images
        if self.image_paths:
            dock_width = self.width()
            margin_space = 80  # Account for margins, scrollbars, and spacing
            available_width = max(250, dock_width - margin_space)

            # Calculate optimal thumbnail size and columns
            min_thumb_size = 70
            max_thumb_size = 160

            # Try different column counts to find best fit
            best_cols = 1
            best_size = min_thumb_size
            best_fit_score = float('inf')

            for cols in range(1, 9):  # Try 1 to 8 columns
                # Calculate thumbnail size for this column count
                thumb_size = (available_width // cols) - 8  # 8px spacing
                thumb_size = max(min_thumb_size, min(max_thumb_size, thumb_size))

                # Calculate total width used
                total_width = cols * (thumb_size + 8)
                # Score how well it fits (lower is better)
                fit_score = abs(available_width - total_width)

                if fit_score < best_fit_score:
                    best_fit_score = fit_score
                    best_cols = cols
                    best_size = thumb_size

            # Update if changed significantly
            if abs(best_size - self.thumbnail_size) > 10:
                self.thumbnail_size = best_size
                self.cols = best_cols
                # Force refresh with new layout
                self.refresh_image_display()


class ConnectionDialog(QDialog):
    def __init__(self, odm_connection, parent=None):
        super().__init__(parent)
        self.odm = odm_connection
        self.setWindowTitle('ODM Connection Settings')
        self.setModal(True)
        self.setFixedSize(300, 150)

        layout = QVBoxLayout()

        # URL input
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel('URL:'))
        self.url_edit = QLineEdit(self.odm.base_url)
        self.url_edit.setPlaceholderText('http://localhost:3000')
        url_layout.addWidget(self.url_edit)
        layout.addLayout(url_layout)

        # Token input
        token_layout = QHBoxLayout()
        token_layout.addWidget(QLabel('Token:'))
        self.token_edit = QLineEdit(self.odm.token)
        self.token_edit.setPlaceholderText('Authentication token (optional)')
        token_layout.addWidget(self.token_edit)
        layout.addLayout(token_layout)

        # Buttons
        button_layout = QHBoxLayout()
        test_btn = QPushButton('Test')
        test_btn.clicked.connect(self.test_connection)
        save_btn = QPushButton('Save')
        save_btn.clicked.connect(self.save_connection)
        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(test_btn)
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

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

    def save_connection(self):
        url = self.url_edit.text().strip()
        token = self.token_edit.text().strip()
        if url and not url.startswith('http://') and not url.startswith('https://'):
            url = 'http://' + url
        self.odm.set_credentials(url, token)
        self.accept()


class ODMDialog(QDockWidget):
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
        self.setMinimumWidth(350)
        self.setMaximumWidth(450)
        # Handle close event to hide instead of close
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        # Create central widget for dock
        central_widget = QWidget()
        self.setWidget(central_widget)

        # Main Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(1)

        # Tab widget
        self.tabs = QTabWidget()

        # Hamburger Menu Button (corner widget inline with tabs)
        self.menu_btn = QPushButton('☰')
        self.menu_btn.setFixedWidth(30)
        self.menu_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #007bff;
                border: none;
                font-size: 16px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                color: #0056b3;
                background-color: #f0f0f0;
            }
        """)
        self.menu_btn.setToolTip('Project Menu')

        # Build the menu
        self.project_menu = QMenu(self)
        connection_action = QAction('🔗 Connection', self)
        connection_action.triggered.connect(self.show_connection_dialog)
        open_action = QAction('📂 Open Project', self)
        open_action.triggered.connect(self.open_project)
        save_action = QAction('💾 Save Project', self)
        save_action.triggered.connect(self.save_project)
        self.project_menu.addAction(connection_action)
        self.project_menu.addSeparator()
        self.project_menu.addAction(open_action)
        self.project_menu.addAction(save_action)

        # Connect button to show menu
        self.menu_btn.setMenu(self.project_menu)

        # Place hamburger menu in top-right corner of tab bar
        self.tabs.setCornerWidget(self.menu_btn)

        # Processing tab - Professional style matching options tab
        self.processing_tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        processing_layout = QVBoxLayout(scroll_content)
        processing_layout.setSpacing(5)
        processing_layout.setContentsMargins(5, 5, 5, 5)

        # Project Settings Group
        project_group = QGroupBox('Project Settings')
        project_grid = QGridLayout()
        project_grid.setContentsMargins(5, 5, 5, 5)
        project_grid.setSpacing(3)

        project_grid.addWidget(QLabel('Processing Preset:'), 0, 0)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            'Default', 'High Resolution', 'Fast Orthophoto',
            'Field', 'DSM+DTM', '3D Model', 'Custom'
        ])
        self.preset_combo.setCurrentText('Default')
        self.preset_combo.currentTextChanged.connect(self.apply_preset)
        self.preset_combo.setToolTip('Choose a processing preset for your project')
        self.preset_combo.setMaximumWidth(180)
        project_grid.addWidget(self.preset_combo, 0, 1)

        project_group.setLayout(project_grid)
        processing_layout.addWidget(project_group)

        # Output Options Group
        output_group = QGroupBox('Output Products')
        output_layout = QVBoxLayout()
        output_layout.setContentsMargins(5, 5, 5, 5)
        output_layout.setSpacing(3)

        output_desc = QLabel('Select outputs:')
        output_desc.setStyleSheet("font-size: 11px; color: #666;")
        output_layout.addWidget(output_desc)

        checkbox_layout = QHBoxLayout()
        checkbox_layout.setSpacing(8)
        self.orthophoto_checkbox = QCheckBox('Orthophoto')
        self.orthophoto_checkbox.setChecked(True)
        self.orthophoto_checkbox.setToolTip('Generate georeferenced orthophoto mosaic')

        self.dsm_checkbox = QCheckBox('DSM')
        self.dsm_checkbox.setToolTip('Generate Digital Surface Model (surface elevation including buildings/vegetation)')

        self.dtm_checkbox = QCheckBox('DTM')
        self.dtm_checkbox.setToolTip('Generate Digital Terrain Model (ground elevation only - includes automatic point cloud classification)')

        checkbox_layout.addWidget(self.orthophoto_checkbox)
        checkbox_layout.addWidget(self.dsm_checkbox)
        checkbox_layout.addWidget(self.dtm_checkbox)
        checkbox_layout.addStretch()

        output_layout.addLayout(checkbox_layout)
        output_group.setLayout(output_layout)
        processing_layout.addWidget(output_group)

        # Input Images Group
        images_group = QGroupBox('Input Images')
        images_layout = QVBoxLayout()
        images_layout.setContentsMargins(5, 5, 5, 5)
        images_layout.setSpacing(3)

        # Compact images info and count
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel('Images:'))

        self.images_count_label = QLabel('0')
        self.images_count_label.setStyleSheet("font-weight: bold; color: #007bff;")
        info_layout.addWidget(self.images_count_label)
        info_layout.addStretch()
        images_layout.addLayout(info_layout)

        # Compact action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(3)

        self.add_images_btn = QPushButton('📁 Add')
        self.add_images_btn.setMaximumWidth(70)
        self.add_images_btn.setToolTip('Select and upload drone images for processing')
        
        # Create dropdown menu for Add button
        self.add_menu = QMenu(self)
        add_files_action = QAction('Add Files', self)
        add_files_action.triggered.connect(self.add_images_from_files)
        add_dir_action = QAction('Add Directory', self)
        add_dir_action.triggered.connect(self.add_images_from_directory)
        self.add_menu.addAction(add_files_action)
        self.add_menu.addAction(add_dir_action)
        self.add_images_btn.setMenu(self.add_menu)

        clear_images_btn = QPushButton('🗑️ Clear')
        clear_images_btn.setMaximumWidth(70)
        clear_images_btn.clicked.connect(self.clear_images)
        clear_images_btn.setToolTip('Remove all uploaded images')

        button_layout.addWidget(self.add_images_btn)
        button_layout.addWidget(clear_images_btn)
        button_layout.addStretch()

        images_layout.addLayout(button_layout)
        images_group.setLayout(images_layout)
        processing_layout.addWidget(images_group)

        # Processing Control Group
        control_group = QGroupBox('Processing Control')
        control_layout = QVBoxLayout()
        control_layout.setContentsMargins(5, 5, 5, 5)
        control_layout.setSpacing(3)

        # Main action buttons - compact
        button_grid = QHBoxLayout()
        button_grid.setSpacing(5)

        self.start_task_btn = QPushButton('🚀 Start')
        self.start_task_btn.clicked.connect(self.start_task_processing)
        self.start_task_btn.setEnabled(False)
        self.start_task_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                font-size: 11px;
                padding: 6px 12px;
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 3px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)

        self.stop_task_btn = QPushButton('🛑 Stop')
        self.stop_task_btn.clicked.connect(self.stop_task)
        self.stop_task_btn.setEnabled(False)
        self.stop_task_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                font-size: 11px;
                padding: 6px 12px;
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 3px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)

        button_grid.addWidget(self.start_task_btn)
        button_grid.addWidget(self.stop_task_btn)
        button_grid.addStretch()

        control_layout.addLayout(button_grid)
        control_group.setLayout(control_layout)
        processing_layout.addWidget(control_group)

        # Status Group
        status_group = QGroupBox('Processing Status')
        status_layout = QVBoxLayout()
        status_layout.setContentsMargins(5, 5, 5, 5)
        status_layout.setSpacing(3)

        self.status_text = QTextEdit()
        self.status_text.setMinimumHeight(50)
        self.status_text.setMaximumHeight(80)
        self.status_text.setReadOnly(True)
        self.status_text.setStyleSheet("""
            QTextEdit {
                font-family: 'Courier New', monospace;
                font-size: 8px;
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 2px;
            }
        """)
        status_layout.addWidget(self.status_text)

        status_group.setLayout(status_layout)
        processing_layout.addWidget(status_group)

        # Add stretch to push everything to top
        processing_layout.addStretch()

        scroll.setWidget(scroll_content)
        tab_layout = QVBoxLayout()
        tab_layout.addWidget(scroll)
        tab_layout.setContentsMargins(0,0,0,0)
        self.processing_tab.setLayout(tab_layout)
        self.tabs.addTab(self.processing_tab, 'Processing')

        # --- OPTIONS TAB (All Options) ---
        self.options_tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        options_tab_layout = QVBoxLayout(scroll_content)
        options_tab_layout.setSpacing(5)
        options_tab_layout.setContentsMargins(5, 5, 5, 5)

        # Group 1: Camera & Reconstruction
        cam_group = QGroupBox('Camera & Reconstruction')
        cam_grid = QGridLayout()
        cam_grid.setContentsMargins(5, 5, 5, 5)
        cam_grid.setSpacing(3)

        cam_grid.addWidget(QLabel('Feature:'), 0, 0)
        self.feature_extraction_combo = QComboBox()
        self.feature_extraction_combo.addItems(['auto', 'high', 'medium', 'low'])
        self.feature_extraction_combo.setMaximumWidth(80)
        cam_grid.addWidget(self.feature_extraction_combo, 0, 1)

        cam_grid.addWidget(QLabel('Lens:'), 0, 2)
        self.camera_lens_combo = QComboBox()
        self.camera_lens_combo.addItems(['auto', 'perspective', 'fisheye', 'spherical'])
        self.camera_lens_combo.setMaximumWidth(90)
        cam_grid.addWidget(self.camera_lens_combo, 0, 3)

        cam_grid.addWidget(QLabel('Quality:'), 1, 0)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(50)
        self.quality_spin.setMaximumWidth(70)
        cam_grid.addWidget(self.quality_spin, 1, 1)

        cam_grid.addWidget(QLabel('Recon:'), 1, 2)
        self.recon_combo = QComboBox()
        self.recon_combo.addItems(['high', 'medium', 'low'])
        self.recon_combo.setCurrentText('high')
        self.recon_combo.setMaximumWidth(80)
        cam_grid.addWidget(self.recon_combo, 1, 3)

        cam_grid.addWidget(QLabel('FOV:'), 2, 0)
        self.fov_spin = QSpinBox()
        self.fov_spin.setRange(1, 180)
        self.fov_spin.setValue(60)
        self.fov_spin.setMaximumWidth(70)
        cam_grid.addWidget(self.fov_spin, 2, 1)

        cam_group.setLayout(cam_grid)
        options_tab_layout.addWidget(cam_group)

        # Group 2: Point Cloud & Filtering
        pc_group = QGroupBox('Point Cloud')
        pc_grid = QGridLayout()
        pc_grid.setContentsMargins(5, 5, 5, 5)
        pc_grid.setSpacing(3)

        pc_grid.addWidget(QLabel('Density:'), 0, 0)
        self.pc_density_combo = QComboBox()
        self.pc_density_combo.addItems(['high', 'medium', 'low'])
        self.pc_density_combo.setCurrentText('medium')
        self.pc_density_combo.setMaximumWidth(80)
        pc_grid.addWidget(self.pc_density_combo, 0, 1)

        pc_grid.addWidget(QLabel('Outlier:'), 1, 0)
        filter_box = QHBoxLayout()
        filter_box.setSpacing(3)
        self.outlier_checkbox = QCheckBox('Enable')
        filter_box.addWidget(self.outlier_checkbox)
        filter_box.addWidget(QLabel('Dev:'))
        self.deviation_spin = QSpinBox()
        self.deviation_spin.setRange(1, 50)
        self.deviation_spin.setValue(5)
        self.deviation_spin.setMaximumWidth(60)
        filter_box.addWidget(self.deviation_spin)
        pc_grid.addLayout(filter_box, 1, 1)

        pc_group.setLayout(pc_grid)
        options_tab_layout.addWidget(pc_group)

        # Group 3: Outputs
        output_group = QGroupBox('Outputs')
        output_grid = QGridLayout()
        output_grid.setContentsMargins(5, 5, 5, 5)
        output_grid.setSpacing(3)

        output_grid.addWidget(QLabel('Resolution:'), 0, 0)
        self.resolution_spin = QSpinBox()
        self.resolution_spin.setRange(1, 100)
        self.resolution_spin.setValue(5)
        self.resolution_spin.setMaximumWidth(70)
        output_grid.addWidget(self.resolution_spin, 0, 1)

        output_grid.addWidget(QLabel('Tile Size:'), 0, 2)
        self.tile_combo = QComboBox()
        self.tile_combo.addItems(['2048', '4096', '8192'])
        self.tile_combo.setCurrentText('2048')
        self.tile_combo.setMaximumWidth(80)
        output_grid.addWidget(self.tile_combo, 0, 3)

        additional_layout = QHBoxLayout()
        additional_layout.setSpacing(6)
        self.texture_checkbox = QCheckBox('Mesh')
        self.texture_checkbox.setChecked(True)
        self.video_checkbox = QCheckBox('Video')
        self.video_checkbox.setChecked(False)
        self.report_checkbox = QCheckBox('Report')
        self.report_checkbox.setChecked(True)

        additional_layout.addWidget(self.texture_checkbox)
        additional_layout.addWidget(self.video_checkbox)
        additional_layout.addWidget(self.report_checkbox)
        output_grid.addLayout(additional_layout, 1, 0, 1, 4)

        output_group.setLayout(output_grid)
        options_tab_layout.addWidget(output_group)

        # Group 4: Performance
        performance_group = QGroupBox('Performance')
        performance_layout = QHBoxLayout()
        performance_layout.setContentsMargins(5, 5, 5, 5)
        performance_layout.setSpacing(3)
        performance_layout.addWidget(QLabel('Threads:'))
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(0, 32)
        self.threads_spin.setValue(0)
        self.threads_spin.setMaximumWidth(60)
        performance_layout.addWidget(self.threads_spin)
        performance_layout.addWidget(QLabel('Memory:'))
        self.memory_spin = QSpinBox()
        self.memory_spin.setRange(1, 64)
        self.memory_spin.setValue(8)
        self.memory_spin.setMaximumWidth(60)
        performance_layout.addWidget(self.memory_spin)
        performance_group.setLayout(performance_layout)
        options_tab_layout.addWidget(performance_group)

        options_tab_layout.addStretch()
        scroll.setWidget(scroll_content)

        tab_main_layout = QVBoxLayout()
        tab_main_layout.addWidget(scroll)
        tab_main_layout.setContentsMargins(0,0,0,0)
        self.options_tab.setLayout(tab_main_layout)

        self.tabs.addTab(self.options_tab, 'Options')

        # GCP tab - Ultra-compact styling
        self.gcp_tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        gcp_layout = QVBoxLayout(scroll_content)
        gcp_layout.setSpacing(5)
        gcp_layout.setContentsMargins(5, 5, 5, 5)

        # GCP file management
        gcp_file_group = QGroupBox('GCP File')
        gcp_file_layout = QVBoxLayout()
        gcp_file_layout.setContentsMargins(5, 5, 5, 5)
        gcp_file_layout.setSpacing(3)

        self.gcp_file_path = QLineEdit()
        self.gcp_file_path.setPlaceholderText('GCP file path (.txt or .csv)')
        self.gcp_file_path.setReadOnly(True)
        self.gcp_file_path.setMaximumHeight(25)
        gcp_file_layout.addWidget(self.gcp_file_path)

        file_btn_layout = QHBoxLayout()
        file_btn_layout.setSpacing(3)
        self.load_gcp_btn = QPushButton('Load')
        self.load_gcp_btn.setMaximumWidth(60)
        self.load_gcp_btn.clicked.connect(self.load_gcp_file)
        self.save_gcp_btn = QPushButton('Save')
        self.save_gcp_btn.setMaximumWidth(60)
        self.save_gcp_btn.clicked.connect(self.save_gcp_file)
        file_btn_layout.addWidget(self.load_gcp_btn)
        file_btn_layout.addWidget(self.save_gcp_btn)
        file_btn_layout.addStretch()
        gcp_file_layout.addLayout(file_btn_layout)

        gcp_file_group.setLayout(gcp_file_layout)

        # GCP point management
        gcp_points_group = QGroupBox('GCP Points')
        gcp_points_layout = QVBoxLayout()
        gcp_points_layout.setContentsMargins(5, 5, 5, 5)
        gcp_points_layout.setSpacing(3)

        self.gcp_list = QListWidget()
        self.gcp_list.setMaximumHeight(80)
        self.gcp_list.setMinimumHeight(50)
        self.gcp_list.itemClicked.connect(self.select_gcp_point)
        gcp_points_layout.addWidget(self.gcp_list)

        # Compact GCP controls
        gcp_controls_layout = QHBoxLayout()
        gcp_controls_layout.setSpacing(3)

        self.add_gcp_btn = QPushButton('Add')
        self.add_gcp_btn.setMaximumWidth(50)
        self.add_gcp_btn.clicked.connect(self.add_gcp_point)

        self.edit_gcp_btn = QPushButton('Edit')
        self.edit_gcp_btn.setMaximumWidth(50)
        self.edit_gcp_btn.clicked.connect(self.edit_gcp_point)
        self.edit_gcp_btn.setEnabled(False)

        self.remove_gcp_btn = QPushButton('Del')
        self.remove_gcp_btn.setMaximumWidth(50)
        self.remove_gcp_btn.clicked.connect(self.remove_gcp_point)
        self.remove_gcp_btn.setEnabled(False)

        gcp_controls_layout.addWidget(self.add_gcp_btn)
        gcp_controls_layout.addWidget(self.edit_gcp_btn)
        gcp_controls_layout.addWidget(self.remove_gcp_btn)
        gcp_controls_layout.addStretch()

        gcp_points_layout.addLayout(gcp_controls_layout)
        gcp_points_group.setLayout(gcp_points_layout)

        # Compact GCP info display
        gcp_info_group = QGroupBox('Point Info')
        gcp_info_layout = QVBoxLayout()
        gcp_info_layout.setContentsMargins(5, 5, 5, 5)
        gcp_info_layout.setSpacing(2)

        info_grid = QGridLayout()
        info_grid.setSpacing(2)

        info_grid.addWidget(QLabel('ID:'), 0, 0)
        self.gcp_id_label = QLabel('-')
        info_grid.addWidget(self.gcp_id_label, 0, 1)

        info_grid.addWidget(QLabel('World:'), 1, 0)
        self.gcp_world_label = QLabel('-, -, -')
        info_grid.addWidget(self.gcp_world_label, 1, 1)

        info_grid.addWidget(QLabel('Image:'), 2, 0)
        self.gcp_image_label = QLabel('-, -')
        info_grid.addWidget(self.gcp_image_label, 2, 1)

        info_grid.addWidget(QLabel('File:'), 3, 0)
        self.gcp_filename_label = QLabel('-')
        info_grid.addWidget(self.gcp_filename_label, 3, 1)

        info_grid.addWidget(QLabel('Name:'), 4, 0)
        self.gcp_name_label = QLabel('-')
        info_grid.addWidget(self.gcp_name_label, 4, 1)

        gcp_info_layout.addLayout(info_grid)
        gcp_info_group.setLayout(gcp_info_layout)

        # Add all groups to GCP layout
        gcp_layout.addWidget(gcp_file_group)
        gcp_layout.addWidget(gcp_points_group)
        gcp_layout.addWidget(gcp_info_group)
        gcp_layout.addStretch()

        scroll.setWidget(scroll_content)
        tab_layout = QVBoxLayout()
        tab_layout.addWidget(scroll)
        tab_layout.setContentsMargins(0,0,0,0)
        self.gcp_tab.setLayout(tab_layout)
        self.tabs.addTab(self.gcp_tab, 'GCPs')

        # Tasks tab - Ultra-compact styling
        self.tasks_tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        tasks_layout = QVBoxLayout(scroll_content)
        tasks_layout.setSpacing(5)
        tasks_layout.setContentsMargins(5, 5, 5, 5)

        # Compact task management
        task_controls_group = QGroupBox('Task Controls')
        task_btn_layout = QHBoxLayout()
        task_btn_layout.setContentsMargins(5, 5, 5, 5)
        task_btn_layout.setSpacing(3)

        self.refresh_tasks_btn = QPushButton('🔄 Refresh')
        self.refresh_tasks_btn.setMaximumWidth(80)
        self.refresh_tasks_btn.clicked.connect(self.load_projects)

        self.delete_task_btn = QPushButton('🗑️ Delete')
        self.delete_task_btn.setMaximumWidth(80)
        self.delete_task_btn.clicked.connect(self.delete_task)
        self.delete_task_btn.setEnabled(False)

        task_btn_layout.addWidget(self.refresh_tasks_btn)
        task_btn_layout.addWidget(self.delete_task_btn)
        task_btn_layout.addStretch()
        task_controls_group.setLayout(task_btn_layout)

        # Active tasks list
        tasks_list_group = QGroupBox('Active Tasks')
        tasks_list_layout = QVBoxLayout()
        tasks_list_layout.setContentsMargins(5, 5, 5, 5)
        tasks_list_layout.setSpacing(3)

        self.projects_list = QListWidget()
        self.projects_list.setMaximumHeight(120)
        self.projects_list.setMinimumHeight(60)
        self.projects_list.itemClicked.connect(self.select_project)
        tasks_list_layout.addWidget(self.projects_list)
        tasks_list_group.setLayout(tasks_list_layout)

        tasks_layout.addWidget(task_controls_group)
        tasks_layout.addWidget(tasks_list_group)
        tasks_layout.addStretch()

        scroll.setWidget(scroll_content)
        tab_layout = QVBoxLayout()
        tab_layout.addWidget(scroll)
        tab_layout.setContentsMargins(0,0,0,0)
        self.tasks_tab.setLayout(tab_layout)
        self.tabs.addTab(self.tasks_tab, 'Tasks')

        # Results tab - Ultra-compact styling
        self.results_tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        results_layout = QVBoxLayout(scroll_content)
        results_layout.setSpacing(5)
        results_layout.setContentsMargins(5, 5, 5, 5)

        # Task selection for Results tab
        results_task_group = QGroupBox('Task Selection')
        results_task_layout = QVBoxLayout()
        results_task_layout.setContentsMargins(5, 5, 5, 5)
        results_task_layout.setSpacing(3)

        self.results_task_combo = QComboBox()
        self.results_task_combo.addItem('No task selected', '')
        self.results_task_combo.currentIndexChanged.connect(self.select_results_task)
        results_task_layout.addWidget(self.results_task_combo)
        results_task_group.setLayout(results_task_layout)

        # Compact action buttons
        results_actions_group = QGroupBox('Actions')
        results_btn_layout = QHBoxLayout()
        results_btn_layout.setContentsMargins(5, 5, 5, 5)
        results_btn_layout.setSpacing(3)

        self.refresh_results_btn = QPushButton('Refresh')
        self.refresh_results_btn.setMaximumWidth(80)
        self.refresh_results_btn.clicked.connect(self.refresh_status)

        self.download_btn = QPushButton('Download')
        self.download_btn.setMaximumWidth(80)
        self.download_btn.clicked.connect(self.download_results)

        self.import_btn = QPushButton('Import')
        self.import_btn.setMaximumWidth(80)
        self.import_btn.clicked.connect(self.import_to_qgis)

        results_btn_layout.addWidget(self.refresh_results_btn)
        results_btn_layout.addWidget(self.download_btn)
        results_btn_layout.addWidget(self.import_btn)
        results_btn_layout.addStretch()
        results_actions_group.setLayout(results_btn_layout)

        # Compact results display
        results_display_group = QGroupBox('Results')
        results_display_layout = QVBoxLayout()
        results_display_layout.setContentsMargins(5, 5, 5, 5)
        results_display_layout.setSpacing(3)

        self.results_text = QTextEdit()
        self.results_text.setMinimumHeight(60)
        self.results_text.setMaximumHeight(100)
        self.results_text.setReadOnly(True)
        results_display_layout.addWidget(self.results_text)
        results_display_group.setLayout(results_display_layout)

        results_layout.addWidget(results_task_group)
        results_layout.addWidget(results_actions_group)
        results_layout.addWidget(results_display_group)
        results_layout.addStretch()

        scroll.setWidget(scroll_content)
        tab_layout = QVBoxLayout()
        tab_layout.addWidget(scroll)
        tab_layout.setContentsMargins(0,0,0,0)
        self.results_tab.setLayout(tab_layout)
        self.tabs.addTab(self.results_tab, 'Results')

        layout.addWidget(self.tabs)
        central_widget.setLayout(layout)

        # Load initial projects
        self.load_projects()

        # Apply default preset on startup
        self.apply_preset('Default')

        # Update images display
        self.update_images_display()

    def closeEvent(self, event):
        # Hide the dock instead of closing it
        event.ignore()
        self.hide()
        
    def show_connection_dialog(self):
        dialog = ConnectionDialog(self.odm, self)
        dialog.exec_()
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
                self.update_images_display()
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
                'feature_extraction': 'high',
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
                'resolution': 5,
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
                'resolution': 2,
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
                'resolution': 20,
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
                'pc_classify': True,  # Essential for proper DTM generation
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
            self.update_images_display()
            self.stop_task_btn.setEnabled(False)
            return

        task_info = self.odm.get_task_info(self.current_project)
        if task_info:
            status_code = task_info.get('status', {}).get('code', 0)
            if status_code == 20:  # RUNNING
                self.start_task_btn.setEnabled(False)
                self.stop_task_btn.setEnabled(True)
            else:
                self.update_images_display()
                self.stop_task_btn.setEnabled(False)
            
    def start_status_monitoring(self):
        if hasattr(self, 'status_timer'):
            self.status_timer.stop()
            
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start(3000)  # Check every 3 seconds
        
        # Initial status check
        self.refresh_status()
            
    def add_images_from_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, 'Select Images', '', 'Image files (*.jpg *.jpeg *.png *.tif *.tiff)')
        for file in files:
            self.image_paths.append(file)
        self.update_images_display()

    def add_images_from_directory(self):
        directory = QFileDialog.getExistingDirectory(self, 'Select Directory with Images')
        if directory:
            image_extensions = ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.JPG', '.JPEG', '.PNG', '.TIF', '.TIFF')
            count = 0
            for filename in os.listdir(directory):
                if filename.lower().endswith(image_extensions):
                    self.image_paths.append(os.path.join(directory, filename))
                    count += 1
            if count == 0:
                QMessageBox.information(self, 'No Images', 'No image files found in the selected directory.')
            self.update_images_display()
            
    def clear_images(self):
        self.image_paths.clear()
        # Also clear images from photo dock if it exists
        if hasattr(self, 'photos_dock') and self.photos_dock:
            self.photos_dock.set_image_paths([])
        self.update_images_display()

    def update_images_display(self):
        """Update the images count and visibility"""
        count = len(self.image_paths)
        self.images_count_label.setText(f'{count} selected')

        # Auto-show photos dock when images are loaded
        if count > 0:
            self.start_task_btn.setEnabled(True)
            if not hasattr(self, 'photos_dock') or self.photos_dock is None:
                # Check if dock already exists in QGIS (from previous session/reload)
                existing_dock = self.iface.mainWindow().findChild(PhotosDock, 'odm_photos_dock')
                if existing_dock:
                    self.photos_dock = existing_dock
                else:
                    self.photos_dock = PhotosDock(self)
                    self.iface.addDockWidget(Qt.LeftDockWidgetArea, self.photos_dock)
                # Show success message after images are loaded
                if hasattr(self, 'pending_project_load_success') and self.pending_project_load_success:
                    QMessageBox.information(self, 'Success', f'Project "{self.project_name}" loaded successfully!')
                    self.pending_project_load_success = False
            self.photos_dock.show()
            self.photos_dock.set_image_paths(self.image_paths)
        else:
            self.start_task_btn.setEnabled(False)


        
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
                options['pc-classify'] = True  # Essential for proper DTM generation
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
            # NOTE: tile_combo (labeled "Tile Size") was previously incorrectly mapped to 'mesh-size'.
            # mesh-size should default to 200000 for good quality.
            # If tile_combo is meant for tiling, we'd use 'tiles': True and maybe other params, but 
            # for now we'll disable the mesh-size override to fix the low-poly mesh issue.
            # options['mesh-size'] = self.tile_combo.currentText() 
            
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
            # Show progress in QGIS message bar
            from qgis.core import Qgis
            self.task_message = self.iface.messageBar().createMessage('ODM: Creating task...')
            self.iface.messageBar().pushWidget(self.task_message, Qgis.Info)
            
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
                # Remove task creation message
                if hasattr(self, 'task_message'):
                    self.iface.messageBar().popWidget(self.task_message)
                    delattr(self, 'task_message')
            
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
            
            # Update QGIS progress/status
            if status_code == 20:  # RUNNING
                # Show progress in QGIS status bar
                self.iface.mainWindow().statusBar().showMessage(f'ODM: {name} - {status_text} ({int(progress)}%)')
                # Show message in QGIS message bar
                if not hasattr(self, 'progress_message'):
                    from qgis.core import Qgis
                    self.progress_message = self.iface.messageBar().createMessage(f'ODM Processing: {name} - {int(progress)}% complete')
                    self.iface.messageBar().pushWidget(self.progress_message, Qgis.Info, 0)
                else:
                    # Update existing message
                    self.progress_message.setText(f'ODM Processing: {name} - {int(progress)}% complete')
            elif status_code in [40, 30, 50]:  # COMPLETED, FAILED, CANCELED
                # Clear progress from status bar
                self.iface.mainWindow().statusBar().clearMessage()
                # Remove progress message from message bar
                if hasattr(self, 'progress_message'):
                    self.iface.messageBar().popWidget(self.progress_message)
                    delattr(self, 'progress_message')
            
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
            for path in self.image_paths:
                if not os.path.exists(path):
                    self.status_text.append(f'⚠ Image not found: {os.path.basename(path)}')
            self.update_images_display()
            
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
            
            # Store project name
            self.project_name = project_data.get('name', 'Loaded Project')

            # Don't show success message yet - wait for images to load
            self.pending_project_load_success = True
            
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
                layout.addWidget(QLabel('Note: Enable DSM/DTM generation in Processing tab before starting task'))
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
            from qgis.core import QgsRasterLayer, QgsVectorLayer, QgsPointCloudLayer, QgsProject
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
                dsm_path = os.path.join(temp_dir, 'odm_dem', 'dsm.tif')
                if os.path.exists(dsm_path):
                    layer = QgsRasterLayer(dsm_path, 'DSM', 'gdal')
                    if layer.isValid():
                        QgsProject.instance().addMapLayer(layer)
                        imported_count += 1
                        self.status_text.append('✓ DSM imported')
                    else:
                        self.status_text.append('DSM file exists but could not be loaded as valid layer')
                else:
                    self.status_text.append('DSM file not found - make sure DSM generation was enabled during processing')

            # DTM
            if options['dtm']:
                dtm_path = os.path.join(temp_dir, 'odm_dem', 'dtm.tif')
                if os.path.exists(dtm_path):
                    layer = QgsRasterLayer(dtm_path, 'DTM', 'gdal')
                    if layer.isValid():
                        QgsProject.instance().addMapLayer(layer)
                        imported_count += 1
                        self.status_text.append('✓ DTM imported')
                    else:
                        self.status_text.append('DTM file exists but could not be loaded as valid layer')
                else:
                    self.status_text.append('DTM file not found - make sure DTM generation was enabled during processing')
                    # List available directories for debugging
                    try:
                        dirs = [d for d in os.listdir(temp_dir) if os.path.isdir(os.path.join(temp_dir, d))]
                        self.status_text.append(f'Available result directories: {dirs}')
                    except:
                        self.status_text.append('Could not list result directories')
                        
            # Point Cloud
            if options['point_cloud']:
                # Try multiple point cloud formats and locations
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
                            imported_count += 1
                            self.status_text.append(f'✓ Point cloud imported from {pc_path}')
                            break  # Found a valid point cloud, stop looking
                        else:
                            self.status_text.append(f'Point cloud file exists at {pc_path} but could not be loaded')
                    else:
                        self.status_text.append(f'Point cloud file not found: {pc_path}')

                if imported_count == 0:  # No point cloud imported
                    self.status_text.append('No valid point cloud files found - make sure point cloud generation was enabled')
                        
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