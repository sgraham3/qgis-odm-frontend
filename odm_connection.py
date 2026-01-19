# -*- coding: utf-8 -*-
import json
import requests
from qgis.PyQt.QtCore import QSettings

class ODMConnection:
    def __init__(self):
        self.settings = QSettings()
        self.base_url = self.settings.value('odm_frontend/base_url', 'http://localhost:3000')
        self.token = self.settings.value('odm_frontend/token', '')
        
    def set_credentials(self, base_url, token=''):
        self.base_url = base_url
        self.token = token
        self.settings.setValue('odm_frontend/base_url', base_url)
        self.settings.setValue('odm_frontend/token', token)
        
    def test_connection(self):
        try:
            # Try NodeODM endpoints
            base_url = self.base_url.rstrip('/')
            endpoints = ['/info', '/', '/task/list']
            for endpoint in endpoints:
                try:
                    response = requests.get(f'{base_url}{endpoint}', timeout=10)
                    if response.status_code == 200:
                        return True
                except:
                    continue
            return False
        except Exception as e:
            print(f"Connection error: {e}")
            return False
            
    def create_task(self, image_paths, options=None, name=None):
        headers = {}
        params = {}
        if self.token:
            params['token'] = self.token
            
        # Ensure base URL doesn't end with slash
        base_url = self.base_url.rstrip('/')
            
        # Create multipart form data for file upload
        files = []
        for path in image_paths:
            files.append(('images', open(path, 'rb')))
            
        # Form data with options
        data = {}
        if options:
            # NodeODM expects options as JSON string array
            import json
            options_array = []
            for key, value in options.items():
                options_array.append({"name": key, "value": value})
            data['options'] = json.dumps(options_array)
        if name:
            data['name'] = name
            
        try:
            response = requests.post(f'{base_url}/task/new',
                                   files=files, data=data, params=params, headers=headers, timeout=60)
            
            # Close all file handles
            for f in files:
                f[1].close()
                
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error creating task: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"Exception creating task: {e}")
            # Close file handles on exception
            for f in files:
                try:
                    f[1].close()
                except:
                    pass
            return None
            
    def get_tasks(self):
        params = {}
        if self.token:
            params['token'] = self.token

        base_url = self.base_url.rstrip('/')
        try:
            # First get the task UUIDs
            response = requests.get(f'{base_url}/task/list',
                                  params=params, timeout=30)
            if response.status_code == 200:
                task_uuids = response.json()

                # For each UUID, get the full task info to include names and status
                tasks_with_info = []
                for task_item in task_uuids:
                    uuid = task_item.get('uuid')
                    if uuid:
                        # Get full task information
                        task_info_response = requests.get(f'{base_url}/task/{uuid}/info',
                                                        params=params, timeout=10)
                        if task_info_response.status_code == 200:
                            task_info = task_info_response.json()
                            tasks_with_info.append(task_info)
                        else:
                            # If we can't get detailed info, at least include the UUID
                            tasks_with_info.append({
                                'uuid': uuid,
                                'name': 'Task',
                                'status': {'code': 0},
                                'progress': 0
                            })
                return tasks_with_info
            else:
                return []
        except Exception as e:
            print(f"Error getting tasks: {e}")
            return []
            
    def upload_images(self, task_id, image_paths):
        # NodeODM uploads images during task creation, so this is not needed
        return True
            
    def start_processing(self, task_id):
        # NodeODM starts processing automatically when task is created
        return True
            
    def get_task_info(self, task_id):
        params = {}
        if self.token:
            params['token'] = self.token
            
        base_url = self.base_url.rstrip('/')
        try:
            response = requests.get(f'{base_url}/task/{task_id}/info',
                                  params=params, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except:
            return None
            
    def download_results(self, task_id, output_path):
        params = {}
        if self.token:
            params['token'] = self.token
            
        base_url = self.base_url.rstrip('/')
        try:
            response = requests.get(f'{base_url}/task/{task_id}/download/all.zip',
                                  params=params, timeout=600, stream=True)
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
            return False
        except:
            return False
    
    def cancel_task(self, task_id):
        """Cancel a running task"""
        params = {}
        if self.token:
            params['token'] = self.token

        base_url = self.base_url.rstrip('/')
        try:
            response = requests.post(f'{base_url}/task/cancel',
                                  params=params,
                                  json={'uuid': task_id},
                                  timeout=30)
            if response.status_code == 200:
                return response.json().get('success', False)
            else:
                print(f"Cancel task error: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"Cancel task exception: {e}")
            return False

    def delete_task(self, task_id):
        """Delete a task"""
        params = {}
        if self.token:
            params['token'] = self.token

        base_url = self.base_url.rstrip('/')
        try:
            response = requests.post(f'{base_url}/task/remove',
                                  params=params,
                                  json={'uuid': task_id},
                                  timeout=30)
            if response.status_code == 200:
                return response.json().get('success', False)
            else:
                print(f"Delete task error: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"Delete task exception: {e}")
            return False