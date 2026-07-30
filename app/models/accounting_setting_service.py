class AccountingSettingService:

    @staticmethod
    def get_account(db, key: str):

        setting = (
            db.query(AccountingSetting)
            .filter(
                AccountingSetting.setting_key == key
            )
            .first()
        )

        if not setting:
            raise Exception(
                f"Accounting setting '{key}' not configured."
            )

        return setting.account_id
