from cryptography.fernet import Fernet, InvalidToken


class SecretCipher:
    def __init__(self, key: str | None) -> None:
        if not key:
            raise ValueError("MODEL_CONFIG_ENCRYPTION_KEY 未配置，无法保存 API Key")
        try:
            self.fernet = Fernet(key.encode("utf-8"))
        except ValueError as exc:
            raise ValueError("MODEL_CONFIG_ENCRYPTION_KEY 格式无效，请使用 Fernet.generate_key() 生成") from exc

    def encrypt(self, secret: str) -> str:
        return self.fernet.encrypt(secret.encode("utf-8")).decode("utf-8")

    def decrypt(self, encrypted: str) -> str:
        try:
            return self.fernet.decrypt(encrypted.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("模型 API Key 解密失败，请重新保存模型配置") from exc
