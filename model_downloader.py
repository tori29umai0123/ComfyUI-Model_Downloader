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
        # INIファイルパスはパラメータで受け取るため、デフォルトは設定しない
        self.node_dir = os.path.dirname(os.path.abspath(__file__))
        
        # config.iniからAPIキーを読み込み
        self.config = self.load_config()
        self.huggingface_token = self.config.get('huggingface_token', '')
        self.civitai_api_key = self.config.get('civitai_api_key', '')
    
    def load_config(self):
        """
        config.iniからAPIキーを読み込み
        
        Returns:
            dict: 設定情報の辞書
        """
        config_path = os.path.join(self.node_dir, "config.ini")
        config_data = {
            'huggingface_token': '',
            'civitai_api_key': ''
        }
        
        if not os.path.exists(config_path):
            print(f"Config file not found: {config_path}")
            print("API keys will need to be provided via UI or you can create config.ini")
            return config_data
        
        config = configparser.ConfigParser()
        try:
            config.read(config_path, encoding='utf-8')
            
            if config.has_section('API_KEYS'):
                if config.has_option('API_KEYS', 'huggingface_token'):
                    config_data['huggingface_token'] = config.get('API_KEYS', 'huggingface_token').strip()
                    if config_data['huggingface_token']:
                        print("✓ Loaded HuggingFace token from config.ini")
                
                if config.has_option('API_KEYS', 'civitai_api_key'):
                    config_data['civitai_api_key'] = config.get('API_KEYS', 'civitai_api_key').strip()
                    if config_data['civitai_api_key']:
                        print("✓ Loaded CivitAI API key from config.ini")
            
        except Exception as e:
            print(f"Warning: Failed to load config.ini: {e}")
        
        return config_data
    
    def normalize_ini_path(self, ini_path):
        """
        INIファイルのパスを正規化
        
        対応する形式:
        - "E:\desktop\model1.ini" (ダブルクォート付き、バックスラッシュ)
        - E:\desktop\model2.ini (クォートなし、バックスラッシュ)
        - E:/desktop/model3.ini (スラッシュ)
        - models.ini (相対パス)
        
        Args:
            ini_path: INIファイルのパス
        
        Returns:
            正規化されたパス
        """
        if not ini_path or not ini_path.strip():
            # 空の場合はカスタムノード直下のmodels.ini
            return os.path.join(self.node_dir, "models.ini")
        
        # 前後の空白を削除
        path = ini_path.strip()
        
        # ダブルクォートとシングルクォートを削除
        if (path.startswith('"') and path.endswith('"')) or \
           (path.startswith("'") and path.endswith("'")):
            path = path[1:-1]
        
        # バックスラッシュをスラッシュに変換（Windowsパス対応）
        path = path.replace('\\', '/')
        
        # 相対パスの場合は絶対パスに変換
        if not os.path.isabs(path):
            # カスタムノードディレクトリからの相対パスとして解釈
            path = os.path.join(self.node_dir, path)
        
        # パスを正規化
        path = os.path.normpath(path)
        
        return path
    
    def save_to_ini(self, url, subdirectory, filename, filepath, expected_hash=""):
        """
        ダウンロードしたモデル情報をINIファイルに保存（バックアップ用）
        常にカスタムノード直下のmodels.iniに保存
        
        Args:
            url: ダウンロード元URL
            subdirectory: 保存先サブディレクトリ
            filename: ファイル名
            filepath: 完全なファイルパス
            expected_hash: SHA-256ハッシュ（オプション）
        """
        ini_path = os.path.join(self.node_dir, "models.ini")
        
        config = configparser.ConfigParser()
        
        # 既存のINIファイルを読み込み
        if os.path.exists(ini_path):
            config.read(ini_path, encoding='utf-8')
        
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
        
        # ディレクトリが存在しない場合は作成
        ini_dir = os.path.dirname(ini_path)
        if ini_dir and not os.path.exists(ini_dir):
            os.makedirs(ini_dir, exist_ok=True)
        
        # INIファイルに書き込み
        with open(ini_path, 'w', encoding='utf-8') as f:
            config.write(f)
        
        print(f"Saved to INI: {ini_path} [section: {section_name}]")
    
    def save_directory_to_ini(self, url, subdirectory, repo_id, revision, directory_path, file_count):
        """
        ダウンロードしたディレクトリ情報をINIファイルに保存（バックアップ用）
        常にカスタムノード直下のmodels.iniに保存
        
        Args:
            url: ディレクトリのURL
            subdirectory: 保存先サブディレクトリ
            repo_id: リポジトリID
            revision: ブランチ/タグ
            directory_path: ディレクトリパス
            file_count: ファイル数
        """
        ini_path = os.path.join(self.node_dir, "models.ini")
        
        config = configparser.ConfigParser()
        
        # 既存のINIファイルを読み込み
        if os.path.exists(ini_path):
            config.read(ini_path, encoding='utf-8')
        
        # セクション名を生成
        dir_name = directory_path.split('/')[-1] if directory_path else repo_id.split('/')[-1]
        base_section = f"DIR_{dir_name.replace('.', '_').replace('/', '_')}"
        section_name = base_section
        counter = 1
        while config.has_section(section_name):
            if config.has_option(section_name, 'url') and config.get(section_name, 'url') == url:
                break
            section_name = f"{base_section}_{counter}"
            counter += 1
        
        # セクションが存在しない場合は作成
        if not config.has_section(section_name):
            config.add_section(section_name)
        
        # 情報を記録
        config.set(section_name, 'type', 'directory')
        config.set(section_name, 'url', url)
        config.set(section_name, 'subdirectory', subdirectory)
        config.set(section_name, 'repo_id', repo_id)
        config.set(section_name, 'revision', revision)
        config.set(section_name, 'directory_path', directory_path if directory_path else '(root)')
        config.set(section_name, 'file_count', str(file_count))
        config.set(section_name, 'timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # ディレクトリが存在しない場合は作成
        ini_dir = os.path.dirname(ini_path)
        if ini_dir and not os.path.exists(ini_dir):
            os.makedirs(ini_dir, exist_ok=True)
        
        # INIファイルに書き込み
        with open(ini_path, 'w', encoding='utf-8') as f:
            config.write(f)
        
        print(f"Saved directory info to INI: {ini_path} [section: {section_name}]")
    
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
                "update_directory_ini": ("BOOLEAN", {
                    "default": False,
                }),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING",)
    RETURN_NAMES = ("status", "file_path",)
    FUNCTION = "download_model"
    CATEGORY = "utils"
    OUTPUT_NODE = True

    def detect_url_type(self, url):
        """URLからダウンロード元とタイプを判定"""
        if "huggingface.co" in url:
            if "/tree/" in url:
                return "huggingface_directory"
            elif "/resolve/" in url or "/blob/" in url:
                return "huggingface"
            else:
                return "huggingface"  # デフォルト
        elif "civitai.com" in url:
            return "civitai"
        else:
            return "unknown"
    
    def parse_huggingface_directory_url(self, url):
        """
        HuggingFaceのディレクトリURLを解析
        
        例: https://huggingface.co/2vXpSwA7/iroiro-lora/tree/main/qwen_lora
        
        Returns:
            tuple: (repo_id, revision, directory_path)
        """
        # URLパターン: https://huggingface.co/{user}/{repo}/tree/{revision}/{path}
        match = re.search(r'huggingface\.co/([^/]+/[^/]+)/tree/([^/]+)(?:/(.+))?', url)
        if match:
            repo_id = match.group(1)
            revision = match.group(2)
            directory_path = match.group(3) if match.group(3) else ""
            return repo_id, revision, directory_path
        return None, None, None
    
    def check_directory_structure_changed(self, url, subdirectory, current_files, update_ini_enabled):
        """
        ディレクトリ構造が変更されたかチェック
        
        Args:
            url: ディレクトリのURL
            subdirectory: 保存先サブディレクトリ
            current_files: 現在のファイルリスト
            update_ini_enabled: INI更新が有効かどうか
        
        Returns:
            bool: INI更新が必要かどうか
        """
        # update_ini_enabledがFalseなら常にFalse
        if not update_ini_enabled:
            return False
        
        ini_path = os.path.join(self.node_dir, "models.ini")
        
        # INIファイルが存在しない場合は更新が必要
        if not os.path.exists(ini_path):
            return True
        
        config = configparser.ConfigParser()
        try:
            config.read(ini_path, encoding='utf-8')
        except:
            return True
        
        # このURLのセクションを探す
        for section in config.sections():
            if config.has_option(section, 'url') and config.get(section, 'url') == url:
                # ファイル数が変わったかチェック
                old_file_count = int(config.get(section, 'file_count', fallback='0'))
                if old_file_count != len(current_files):
                    print(f"Directory structure changed: file count {old_file_count} → {len(current_files)}")
                    return True
                
                # サブディレクトリが変わったかチェック
                old_subdir = config.get(section, 'subdirectory', fallback='')
                if old_subdir != subdirectory:
                    print(f"Directory structure changed: subdirectory '{old_subdir}' → '{subdirectory}'")
                    return True
                
                # 変更なし
                print(f"Directory structure unchanged (INI update disabled or no changes)")
                return False
        
        # セクションが見つからない場合は新規作成が必要
        return True
    
    def get_directory_files(self, repo_id, revision="main", directory_path=""):
        """
        HuggingFaceのディレクトリ内のファイル一覧を取得
        
        Args:
            repo_id: リポジトリID (例: "2vXpSwA7/iroiro-lora")
            revision: ブランチ/タグ (例: "main")
            directory_path: ディレクトリパス (例: "qwen_lora")
        
        Returns:
            list: ファイル情報のリスト
        """
        # HuggingFace API を使用
        if directory_path:
            api_url = f"https://huggingface.co/api/models/{repo_id}/tree/{revision}/{directory_path}"
        else:
            api_url = f"https://huggingface.co/api/models/{repo_id}/tree/{revision}"
        
        print(f"Fetching file list from: {api_url}")
        
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            # HuggingFaceトークンが設定されている場合は使用
            if self.huggingface_token:
                headers["Authorization"] = f"Bearer {self.huggingface_token}"
            
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            items = response.json()
            
            # ファイルのみを抽出（再帰的にサブディレクトリも取得）
            files = []
            for item in items:
                if item.get('type') == 'file':
                    files.append(item)
                elif item.get('type') == 'directory':
                    # サブディレクトリの場合は再帰的に取得
                    subdir_path = item.get('path')
                    if directory_path:
                        full_subdir_path = f"{directory_path}/{subdir_path}"
                    else:
                        full_subdir_path = subdir_path
                    
                    # 再帰的に取得
                    sub_files = self.get_directory_files(repo_id, revision, full_subdir_path)
                    files.extend(sub_files)
            
            return files
            
        except Exception as e:
            print(f"Error fetching directory files: {e}")
            return []
    
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
    
    def download_directory(self, url, subdirectory, expected_hash="", max_retries=3, update_directory_ini=False):
        """
        HuggingFaceのディレクトリ全体をダウンロード
        
        Args:
            url: ディレクトリのURL
            subdirectory: 保存先サブディレクトリ
            expected_hash: （ディレクトリの場合は使用しない）
            max_retries: 最大リトライ回数
            update_directory_ini: ディレクトリ構造変更時にINIを更新するか（デフォルト: False）
        
        Returns:
            tuple: (status, file_paths)
        """
        # URLを解析
        repo_id, revision, directory_path = self.parse_huggingface_directory_url(url)
        
        if not repo_id:
            return ("Error: Invalid HuggingFace directory URL", [])
        
        print(f"\n{'='*70}")
        print(f"Downloading directory from HuggingFace")
        print(f"{'='*70}")
        print(f"Repository: {repo_id}")
        print(f"Revision: {revision}")
        print(f"Directory: {directory_path if directory_path else '(root)'}")
        print(f"Save to: {subdirectory}")
        print(f"Update INI: {update_directory_ini}")
        print(f"{'='*70}\n")
        
        # ファイル一覧を取得
        files = self.get_directory_files(repo_id, revision, directory_path)
        
        if not files:
            return (f"Error: No files found in directory", [])
        
        print(f"Found {len(files)} file(s) to download\n")
        
        # INI更新が必要かチェック
        should_update_ini = self.check_directory_structure_changed(
            url, subdirectory, files, update_directory_ini
        )
        
        # 結果を記録
        downloaded_files = []
        failed_files = []
        skipped_files = []
        
        # 各ファイルをダウンロード
        for idx, file_info in enumerate(files, 1):
            file_path_in_repo = file_info.get('path')
            
            # ファイル名を取得
            filename = os.path.basename(file_path_in_repo)
            
            # ディレクトリパスから相対パスを計算
            if directory_path:
                # directory_path以下の相対パスを取得
                if file_path_in_repo.startswith(directory_path + '/'):
                    relative_path = file_path_in_repo[len(directory_path) + 1:]
                elif file_path_in_repo.startswith(directory_path):
                    relative_path = file_path_in_repo[len(directory_path):]
                else:
                    relative_path = file_path_in_repo
            else:
                relative_path = file_path_in_repo
            
            # 保存先のサブディレクトリを決定（元のディレクトリ構造を維持）
            file_subdir_parts = os.path.dirname(relative_path).split('/')
            if file_subdir_parts and file_subdir_parts[0]:
                file_subdirectory = os.path.join(subdirectory, *file_subdir_parts)
            else:
                file_subdirectory = subdirectory
            
            print(f"[{idx}/{len(files)}] {relative_path}")
            
            # 保存先のフルパスを計算
            try:
                normalized_subdir = self.normalize_and_validate_path(file_subdirectory)
                target_dir = os.path.join(self.base_path, normalized_subdir)
                target_filepath = os.path.join(target_dir, filename)
            except ValueError as e:
                print(f"  ✗ Error: Invalid path - {e}\n")
                failed_files.append(file_path_in_repo)
                continue
            
            # 既存ファイルのチェック
            if os.path.exists(target_filepath):
                print(f"  ⊘ Skipped: {filename} (already exists)\n")
                skipped_files.append(file_path_in_repo)
                continue
            
            # ダウンロードURL生成
            file_url = f"https://huggingface.co/{repo_id}/resolve/{revision}/{file_path_in_repo}"
            
            # ダウンロード実行
            status, filepath = self.download_model(
                url=file_url,
                subdirectory=file_subdirectory,
                filename=filename,
                expected_hash="",  # ディレクトリダウンロード時は個別ファイルのハッシュ検証なし
                max_retries=max_retries
            )
            
            if filepath and "Error" not in status:
                downloaded_files.append(filepath)
                print(f"  ✓ Success: {filename}\n")
            elif "already exists" in status:
                # download_modelで既にスキップされた場合（二重チェック）
                skipped_files.append(file_path_in_repo)
                print(f"  ⊘ Skipped: {filename} (already exists)\n")
            else:
                failed_files.append(file_path_in_repo)
                print(f"  ✗ Failed: {filename}\n")
        
        # サマリーを表示
        print("\n" + "="*70)
        print("DIRECTORY DOWNLOAD SUMMARY")
        print("="*70)
        print(f"Total files:     {len(files)}")
        print(f"✓ Downloaded:    {len(downloaded_files)}")
        print(f"⊘ Skipped:       {len(skipped_files)}")
        print(f"✗ Failed:        {len(failed_files)}")
        
        if failed_files:
            print(f"\nFailed files:")
            for f in failed_files:
                print(f"  - {f}")
        
        print("="*70)
        
        # ディレクトリ情報をINIに保存（構造変更時のみ、または初回）
        if should_update_ini:
            try:
                self.save_directory_to_ini(url, subdirectory, repo_id, revision, directory_path, len(files))
                print(f"✓ Updated models.ini with directory information")
            except Exception as e:
                print(f"Warning: Failed to save directory info to INI: {e}")
        else:
            print(f"⊘ Skipped INI update (update_directory_ini={update_directory_ini})")
        
        # 結果メッセージ
        if failed_files:
            status_msg = f"⚠ Directory download completed with errors: {len(downloaded_files)} downloaded, {len(skipped_files)} skipped, {len(failed_files)} failed"
        else:
            status_msg = f"✓ Directory download completed: {len(downloaded_files)} downloaded, {len(skipped_files)} skipped"
        
        return (status_msg, downloaded_files)

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
                # HuggingFaceトークンがconfig.iniに設定されている場合は使用
                if self.huggingface_token:
                    headers["Authorization"] = f"Bearer {self.huggingface_token}"
                    print("✓ Using HuggingFace token from config.ini")
            elif url_type == "civitai":
                # CivitAI用のヘッダー
                headers = {"User-Agent": "Mozilla/5.0"}
                # config.iniからCivitAI APIキーを使用
                if self.civitai_api_key:
                    headers["Authorization"] = f"Bearer {self.civitai_api_key}"
                    print("✓ Using CivitAI API key from config.ini")
                else:
                    print("⚠ No CivitAI API key found in config.ini (may fail for some models)")
            
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
    
    def download_model(self, url, subdirectory, filename="", expected_hash="", max_retries=3, update_directory_ini=False):
        """モデルをダウンロードするメイン関数"""
        
        # URL検証
        if not url:
            return ("Error: URL is empty", "")
        
        # URL種別判定
        url_type = self.detect_url_type(url)
        if url_type == "unknown":
            return (f"Error: Unsupported URL. Only HuggingFace and CivitAI are supported.", "")
        
        # HuggingFaceディレクトリの場合は専用メソッドを呼び出し
        if url_type == "huggingface_directory":
            return self.download_directory(url, subdirectory, expected_hash, max_retries, update_directory_ini)
        
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
                
                # INIファイルに保存（バックアップ用）
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
                "update_directory_ini": ("BOOLEAN", {
                    "default": False,
                }),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING",)
    RETURN_NAMES = ("status", "summary",)
    FUNCTION = "download_from_ini"
    CATEGORY = "utils"
    OUTPUT_NODE = True
    
    def download_from_ini(self, ini_file_path="", max_retries=3, skip_existing=True, update_directory_ini=False):
        """
        INIファイルからモデルを一括ダウンロード
        
        Args:
            ini_file_path: INIファイルのパス（空の場合はデフォルト位置）
            max_retries: 最大リトライ回数
            skip_existing: 既存ファイルをスキップするか
            update_directory_ini: ディレクトリ構造変更時にINIを更新するか
        """
        # ModelDownloaderインスタンスを作成（パス正規化に使用）
        downloader = ModelDownloader()
        
        # INIファイルパスの正規化
        ini_path = downloader.normalize_ini_path(ini_file_path)
        
        print(f"Using INI file: {ini_path}")
        
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
                item_type = config.get(section, 'type', fallback='file')
                
                print(f"Type: {item_type}")
                print(f"URL: {url}")
                print(f"Subdirectory: {subdirectory}")
                if item_type != 'directory':
                    print(f"Filename: {filename}")
                if expected_hash:
                    print(f"Hash: {expected_hash[:16]}...")
                
                # ディレクトリタイプの場合はファイル存在チェックをスキップ
                if skip_existing and filename and item_type != 'directory':
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
                    max_retries=max_retries,
                    update_directory_ini=update_directory_ini
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
