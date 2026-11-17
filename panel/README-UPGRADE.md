# به‌روزرسانی دستی پنل

نسخهٔ ۳.۱.۰ ادامهٔ خط نسخهٔ ۳ است. این بسته اطلاعات ورود، پایگاه‌داده و گواهی HTTPS قبلی را حفظ می‌کند و راه‌اندازی به‌روزرسانی آنلاین را هم اصلاح می‌کند.

1. ZIP را در سرور بارگذاری و در `/home/rustdesk/rustdesk-server` استخراج کنید.
2. در PuTTY وارد پوشه شوید و اجرا کنید:

```bash
cd /home/rustdesk/rustdesk-server/panel
sudo bash upgrade.sh
```

3. وضعیت سرویس را بررسی کنید:

```bash
sudo systemctl status rustdeskpanel.service --no-pager -l
```

برای نصب تازه، از `install.sh` استفاده می‌شود. برای نصب موجود، `install.sh` را دوباره اجرا نکنید؛ از `upgrade.sh` استفاده کنید.
