import os
import hashlib
import requests
from urllib.parse import urlparse
import folder_paths
import re
import configparser
from datetime import datetime

class ModelDownloader:
    """
    ComfyUI用モデルダウンローダーノード
    HuggingFaceとCivitAIからモデルをダウンロード
    """
    
    def __init__(self):
        self.base_path = folder_paths.models_dir
        # INIファイルはカスタムノードディレクトリ直下に配置
        self.node_dir = os.path.dirname(os.path.abspath(__file__))
        self.ini_path = os.path.join(self.node_dir, "models.ini")
    
    def save_to_ini(self, url, subdirectory, filename, filepath, expected_hash=""):
        """
        ダウンロードしたモデル情報をINIファイルに保存
        
        Args:
            url: ダウンロード元URL
            subdirectory: 保存先サブディレクトリ
            filename: ファイル名
            filepath: 完全なファイルパス
            expected_hash: SHA-256ハッシュ（オプション）
        """
        config = configparser.ConfigParser()
        
        # 既存のINIファイルを読み込み
        if os.path.exists(self.ini_path):
            config.read(self.ini_path, encoding='utf-8')
        
        # セクション名を生成（ファイル名ベース、重複回避）
        base_section = filename.replace('.', '_')
        section_name = base_section
        counter = 1
        while config.has_section(section_name):
            # 既存のセクションと同じURLなら更新、異なるなら新規セクション
            if config.has_option(section_name, 'url') and config.get(section_name, 'url') == url:
                break
            section_name = f"{base_section}_{counter}"
            counter += 1
        
        # セクションが存在しない場合は作成
        if not config.has_section(section_name):
            config.add_section(section_name)
        
        # 情報を記録
        config.set(section_name, 'url', url)
        config.set(section_name, 'subdirectory', subdirectory)
        config.set(section_name, 'filename', filename)
        config.set(section_name, 'filepath', os.path.relpath(filepath, self.base_path))
        if expected_hash:
            config.set(section_name, 'hash', expected_hash)
        config.set(section_name, 'timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # INIファイルに書き込み
        with open(self.ini_path, 'w', encoding='utf-8') as f:
            config.write(f)
        
        print(f"Saved to INI: {self.ini_path} [section: {section_name}]")    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "HuggingFace or CivitAI URL"
                }),
                "subdirectory": ("STRING", {
                    "default": "checkpoints",
                    "multiline": False,
                    "placeholder": "e.g., checkpoints, loras/SDXL, controlnet/lineart"
                }),
                "filename": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "Output filename (optional, auto-detect if empty)"
                }),
            },
            "optional": {
                "expected_hash": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "SHA-256 hash for verification (optional)"
                }),
                "max_retries": ("INT", {
                    "default": 3,
                    "min": 1,
                    "max": 10,
                    "step": 1
                }),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING",)
    RETURN_NAMES = ("status", "file_path",)
    FUNCTION = "download_model"
    CATEGORY = "utils"
    OUTPUT_NODE = True

    def detect_url_type(self, url):
        """URLからダウンロード元を判定"""
        if "huggingface.co" in url:
            return "huggingface"
        elif "civitai.com" in url:
            return "civitai"
        else:
            return "unknown"
    
    def extract_filename_from_url(self, url, url_type):
        """URLからファイル名を抽出"""
        if url_type == "huggingface":
            # HuggingFace: /resolve/main/filename.safetensors
            match = re.search(r'/resolve/[^/]+/(.+?)(?:\?|$)', url)
            if match:
                return match.group(1).split('/')[-1]
        elif url_type == "civitai":
            # CivitAI: ヘッダーから取得するため、ここではデフォルト名
            return None
        
        # フォールバック: URLの最後の部分
        return os.path.basename(urlparse(url).path)
    
    def normalize_and_validate_path(self, subdirectory):
        """
        サブディレクトリのパスを正規化し、安全性をチェック
        
        Args:
            subdirectory: ユーザー指定のサブディレクトリパス（例: "loras/SDXL"）
        
        Returns:
            正規化されたパス
        
        Raises:
            ValueError: 危険なパスが指定された場合
        """
        # 空の場合はデフォルト
        if not subdirectory or not subdirectory.strip():
            return "checkpoints"
        
        # 絶対パスの禁止（処理前にチェック）
        if os.path.isabs(subdirectory):
            raise ValueError(
                f"Invalid path: '{subdirectory}'. "
                "Absolute paths are not allowed. Use relative paths only."
            )
        
        # Windowsの絶対パス（ドライブレター）のチェック
        # 例: C:, D:, C:\, C:/
        if len(subdirectory) >= 2 and subdirectory[1] == ':':
            raise ValueError(
                f"Invalid path: '{subdirectory}'. "
                "Absolute paths (including drive letters) are not allowed. Use relative paths only."
            )
        
        # セキュリティチェック: ディレクトリトラバーサル攻撃の防止（正規化前にチェック）
        # ".." が含まれていないかチェック
        if '..' in subdirectory:
            raise ValueError(
                f"Invalid path: '{subdirectory}'. "
                "Parent directory references (..) are not allowed for security reasons."
            )
        
        # パスの正規化（Windows/Unix両対応）
        normalized = os.path.normpath(subdirectory)
        
        # バックスラッシュをスラッシュに変換（Windows対応）
        normalized = normalized.replace('\\', '/')
        
        # 先頭のスラッシュを削除
        normalized = normalized.lstrip('/')
        
        # 末尾のスラッシュを削除
        normalized = normalized.rstrip('/')
        
        # 正規化後も空になっていないかチェック
        if not normalized:
            return "checkpoints"
        
        # 正規化後に ".." が含まれていないか再度チェック
        if '..' in normalized:
            raise ValueError(
                f"Invalid path: '{subdirectory}'. "
                "Parent directory references (..) are not allowed for security reasons."
            )
        
        # パスの各部分をチェック（空の部分は許可しない）
        parts = normalized.split('/')
        for part in parts:
            if not part:
                raise ValueError(
                    f"Invalid path: '{subdirectory}'. "
                    "Empty path components are not allowed."
                )
        
        return normalized
    
    def calculate_sha256(self, filepath, chunk_size=8192):
        """ファイルのSHA-256ハッシュを計算"""
        sha256_hash = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                while chunk := f.read(chunk_size):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            print(f"Hash calculation error: {e}")
            return None
    
    def verify_hash(self, filepath, expected_hash):
        """ハッシュ検証"""
        if not expected_hash:
            return True
        
        actual_hash = self.calculate_sha256(filepath)
        if actual_hash is None:
            return False
        
        # ハッシュ比較（大文字小文字を無視）
        match = actual_hash.lower() == expected_hash.lower()
        if not match:
            print(f"Hash mismatch!")
            print(f"Expected: {expected_hash}")
            print(f"Actual:   {actual_hash}")
        return match
    
    def download_file(self, url, filepath, url_type):
        """ファイルをダウンロード"""
        try:
            print(f"Downloading from {url_type.upper()}...")
            print(f"URL: {url}")
            print(f"Destination: {filepath}")
            
            headers = {}
            if url_type == "huggingface":
                headers = {"User-Agent": "Mozilla/5.0"}
            
            response = requests.get(url, headers=headers, stream=True, allow_redirects=True)
            response.raise_for_status()
            
            # CivitAIの場合、Content-Dispositionからファイル名を取得
            if url_type == "civitai" and "content-disposition" in response.headers:
                content_disp = response.headers["content-disposition"]
                filename_match = re.search(r'filename="?([^"]+)"?', content_disp)
                if filename_match:
                    suggested_filename = filename_match.group(1)
                    # ファイル名が指定されていない場合は、suggested_filenameを使用
                    if not os.path.basename(filepath):
                        filepath = os.path.join(os.path.dirname(filepath), suggested_filename)
            
            # ファイルサイズ取得
            total_size = int(response.headers.get('content-length', 0))
            
            # ダウンロード実行
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'wb') as f:
                if total_size == 0:
                    f.write(response.content)
                else:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            # 進捗表示
                            percent = (downloaded / total_size) * 100
                            print(f"\rProgress: {percent:.1f}% ({downloaded}/{total_size} bytes)", end="")
                    print()  # 改行
            
            return filepath
            
        except Exception as e:
            print(f"Download error: {e}")
            if os.path.exists(filepath):
                os.remove(filepath)
            raise
    
    def download_model(self, url, subdirectory, filename="", expected_hash="", max_retries=3):
        """モデルをダウンロードするメイン関数"""
        
        # URL検証
        if not url:
            return ("Error: URL is empty", "")
        
        # URL種別判定
        url_type = self.detect_url_type(url)
        if url_type == "unknown":
            return (f"Error: Unsupported URL. Only HuggingFace and CivitAI are supported.", "")
        
        # サブディレクトリパスの正規化と検証
        try:
            normalized_subdir = self.normalize_and_validate_path(subdirectory)
            print(f"Subdirectory: {subdirectory} -> {normalized_subdir}")
        except ValueError as e:
            return (f"Error: {str(e)}", "")
        
        # ファイル名決定
        if not filename:
            filename = self.extract_filename_from_url(url, url_type)
            if not filename:
                filename = "downloaded_model.safetensors"
        
        # 保存先パス構築（正規化されたサブディレクトリを使用）
        target_dir = os.path.join(self.base_path, normalized_subdir)
        filepath = os.path.join(target_dir, filename)
        
        print(f"Target directory: {target_dir}")
        print(f"Full path: {filepath}")
        
        # ディレクトリ作成（ネストされたディレクトリも自動作成）
        os.makedirs(target_dir, exist_ok=True)
        
        # ダウンロード（リトライ機能付き）
        for attempt in range(1, max_retries + 1):
            try:
                print(f"\n{'='*60}")
                print(f"Attempt {attempt}/{max_retries}")
                print(f"{'='*60}")
                
                # 既存ファイルのチェック
                if os.path.exists(filepath):
                    print(f"File already exists: {filepath}")
                    print("Verifying hash...")
                    
                    if self.verify_hash(filepath, expected_hash):
                        print("Hash verification successful!")
                        
                        # INIファイルに保存（既存ファイルでも記録）
                        try:
                            self.save_to_ini(url, subdirectory, filename, filepath, expected_hash)
                        except Exception as e:
                            print(f"Warning: Failed to save to INI file: {e}")
                        
                        return (
                            f"✓ File already exists and verified: {os.path.basename(filepath)}",
                            filepath
                        )
                    else:
                        print("Hash verification failed. Re-downloading...")
                        os.remove(filepath)
                
                # ダウンロード実行
                downloaded_path = self.download_file(url, filepath, url_type)
                
                # ハッシュ検証
                if expected_hash:
                    print("Verifying hash...")
                    if not self.verify_hash(downloaded_path, expected_hash):
                        if attempt < max_retries:
                            print(f"Hash mismatch. Retrying... ({attempt}/{max_retries})")
                            os.remove(downloaded_path)
                            continue
                        else:
                            os.remove(downloaded_path)
                            return (
                                f"Error: Hash verification failed after {max_retries} attempts",
                                ""
                            )
                    else:
                        print("Hash verification successful!")
                
                # 成功
                success_msg = f"✓ Successfully downloaded: {os.path.basename(downloaded_path)}"
                
                # INIファイルに保存
                try:
                    self.save_to_ini(url, subdirectory, filename, downloaded_path, expected_hash)
                except Exception as e:
                    print(f"Warning: Failed to save to INI file: {e}")
                
                return (success_msg, downloaded_path)
                
            except Exception as e:
                error_msg = str(e)
                if attempt < max_retries:
                    print(f"Attempt {attempt} failed: {error_msg}")
                    print("Retrying...")
                else:
                    return (
                        f"Error: Download failed after {max_retries} attempts - {error_msg}",
                        ""
                    )
        
        return ("Error: Unknown error occurred", "")


class ModelDownloaderFromINI:
    """
    models.iniファイルからモデルを一括ダウンロード
    """
    
    def __init__(self):
        self.base_path = folder_paths.models_dir
        # INIファイルはカスタムノードディレクトリ直下に配置
        self.node_dir = os.path.dirname(os.path.abspath(__file__))
        self.default_ini_path = os.path.join(self.node_dir, "models.ini")
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "ini_file_path": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "Path to models.ini (empty = use default location)"
                }),
            },
            "optional": {
                "max_retries": ("INT", {
                    "default": 3,
                    "min": 1,
                    "max": 10,
                    "step": 1
                }),
                "skip_existing": ("BOOLEAN", {
                    "default": True,
                }),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING",)
    RETURN_NAMES = ("status", "summary",)
    FUNCTION = "download_from_ini"
    CATEGORY = "utils"
    OUTPUT_NODE = True
    
    def download_from_ini(self, ini_file_path="", max_retries=3, skip_existing=True):
        """
        INIファイルからモデルを一括ダウンロード
        
        Args:
            ini_file_path: INIファイルのパス（空の場合はデフォルト位置）
            max_retries: 最大リトライ回数
            skip_existing: 既存ファイルをスキップするか
        """
        # INIファイルパスの決定
        if not ini_file_path or not ini_file_path.strip():
            ini_path = self.default_ini_path
        else:
            ini_path = ini_file_path
        
        # INIファイルの存在チェック
        if not os.path.exists(ini_path):
            return (
                f"Error: INI file not found: {ini_path}",
                ""
            )
        
        # INIファイルを読み込み
        config = configparser.ConfigParser()
        try:
            config.read(ini_path, encoding='utf-8')
        except Exception as e:
            return (
                f"Error: Failed to read INI file: {e}",
                ""
            )
        
        if not config.sections():
            return (
                f"Error: No models found in INI file: {ini_path}",
                ""
            )
        
        print("="*70)
        print(f"Loading models from INI: {ini_path}")
        print(f"Found {len(config.sections())} model(s)")
        print("="*70)
        
        # ModelDownloaderインスタンスを作成
        downloader = ModelDownloader()
        
        # 結果を記録
        results = {
            'total': len(config.sections()),
            'success': 0,
            'skipped': 0,
            'failed': 0,
            'failed_models': []
        }
        
        # 各モデルをダウンロード
        for section in config.sections():
            print(f"\n{'='*70}")
            print(f"Processing: {section}")
            print(f"{'='*70}")
            
            try:
                # 必須フィールドの取得
                if not config.has_option(section, 'url'):
                    print(f"Error: Missing 'url' in section [{section}]")
                    results['failed'] += 1
                    results['failed_models'].append(section)
                    continue
                
                url = config.get(section, 'url')
                subdirectory = config.get(section, 'subdirectory', fallback='checkpoints')
                filename = config.get(section, 'filename', fallback='')
                expected_hash = config.get(section, 'hash', fallback='')
                
                print(f"URL: {url}")
                print(f"Subdirectory: {subdirectory}")
                print(f"Filename: {filename}")
                if expected_hash:
                    print(f"Hash: {expected_hash[:16]}...")
                
                # ファイルの存在チェック
                if skip_existing and filename:
                    target_path = os.path.join(self.base_path, subdirectory, filename)
                    if os.path.exists(target_path):
                        print(f"Skipping: File already exists")
                        results['skipped'] += 1
                        continue
                
                # ダウンロード実行
                status, filepath = downloader.download_model(
                    url=url,
                    subdirectory=subdirectory,
                    filename=filename,
                    expected_hash=expected_hash,
                    max_retries=max_retries
                )
                
                if filepath and "Error" not in status:
                    results['success'] += 1
                    print(f"✓ Success: {section}")
                else:
                    results['failed'] += 1
                    results['failed_models'].append(section)
                    print(f"✗ Failed: {section}")
                    print(f"  Status: {status}")
                
            except Exception as e:
                print(f"✗ Error processing [{section}]: {e}")
                results['failed'] += 1
                results['failed_models'].append(section)
        
        # サマリーを生成
        print("\n" + "="*70)
        print("DOWNLOAD SUMMARY")
        print("="*70)
        print(f"Total models:    {results['total']}")
        print(f"✓ Success:       {results['success']}")
        print(f"⊘ Skipped:       {results['skipped']}")
        print(f"✗ Failed:        {results['failed']}")
        
        if results['failed_models']:
            print(f"\nFailed models:")
            for model in results['failed_models']:
                print(f"  - {model}")
        
        print("="*70)
        
        # 結果メッセージを作成
        status_msg = f"Completed: {results['success']} success, {results['skipped']} skipped, {results['failed']} failed"
        
        summary = (
            f"Total: {results['total']}\n"
            f"Success: {results['success']}\n"
            f"Skipped: {results['skipped']}\n"
            f"Failed: {results['failed']}"
        )
        
        if results['failed'] == 0:
            return (f"✓ {status_msg}", summary)
        else:
            return (f"⚠ {status_msg}", summary)


# ノード登録
NODE_CLASS_MAPPINGS = {
    "ModelDownloader": ModelDownloader,
    "ModelDownloaderFromINI": ModelDownloaderFromINI
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModelDownloader": "Model Downloader (HF/CivitAI)",
    "ModelDownloaderFromINI": "Model Downloader from INI"
}
