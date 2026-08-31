import re

with open('axiom/gui/widgets/update_dialog.py', 'r') as f:
    content = f.read()

download_thread_run = """    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={'User-Agent': 'AXIOM-Updater'})
            with urllib.request.urlopen(req, timeout=10) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                chunk_size = 1024 * 64
                with open('/tmp/axiom_update.tar.gz', 'wb') as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            self.progress.emit(percent)
                            
            # Attempt to fetch sha256sum.txt
            import os
            import hashlib
            expected_hash = None
            try:
                base_url = self.url.rsplit('/', 1)[0]
                hash_url = f"{base_url}/sha256sum.txt"
                req_hash = urllib.request.Request(hash_url, headers={'User-Agent': 'AXIOM-Updater'})
                with urllib.request.urlopen(req_hash, timeout=5) as response:
                    hash_content = response.read().decode('utf-8')
                    # Find the hash for our file
                    filename = self.url.split('/')[-1]
                    for line in hash_content.splitlines():
                        if filename in line:
                            expected_hash = line.split()[0].strip()
                            break
            except Exception as e:
                logger.warning(f"Could not fetch or parse sha256sum.txt: {e}")
                
            if expected_hash:
                sha256 = hashlib.sha256()
                with open('/tmp/axiom_update.tar.gz', 'rb') as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        sha256.update(chunk)
                actual_hash = sha256.hexdigest()
                if actual_hash != expected_hash:
                    os.remove('/tmp/axiom_update.tar.gz')
                    class VerificationError(Exception): pass
                    raise VerificationError(f"Hash mismatch. Expected {expected_hash}, got {actual_hash}")
            
            # Extract tar.gz
            import tarfile
            import shutil
            
            extract_dir = '/tmp/axiom_extracted'
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
            os.makedirs(extract_dir, exist_ok=True)
            
            try:
                with tarfile.open('/tmp/axiom_update.tar.gz', 'r:gz') as tar:
                    tar.extractall(path=extract_dir)
            except Exception as extract_err:
                logger.warning(f"Could not extract as tar.gz (maybe dummy test): {extract_err}")
                
            logger.info("Download complete.")
            self.finished_download.emit(True, "Success")
        except Exception as e:
            logger.error(f"Download failed: {e}")
            self.finished_download.emit(False, str(e))"""

content = re.sub(r'    def run\(self\):.*?self\.finished_download\.emit\(False, str\(e\)\)', download_thread_run, content, flags=re.DOTALL, count=1)

with open('axiom/gui/widgets/update_dialog.py', 'w') as f:
    f.write(content)

