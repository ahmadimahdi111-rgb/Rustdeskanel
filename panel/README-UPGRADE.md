# به‌روزرسانی دستی پنل

این بسته اطلاعات ورود، پایگاه‌داده و گواهی HTTPS قبلی را حفظ می‌کند.

1. فایل ZIP را در سرور بارگذاری و در پوشه‌ای مانند `/home/rustdesk/rustdesk-server` استخراج کنید.
2. وارد پوشه `panel` شوید و اجرا کنید:

```bash
sudo bash upgrade.sh
```

3. وضعیت سرویس را بررسی کنید:

```bash
sudo systemctl status rustdeskpanel.service --no-pager -l
```

برای نصب تازه، از `install.sh` استفاده می‌شود. برای نصب موجود، `install.sh` را دوباره اجرا نکنید؛ از `upgrade.sh` استفاده کنید.
