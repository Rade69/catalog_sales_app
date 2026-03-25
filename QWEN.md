## Qwen Added Memories
- Project catalog_sales_app: v0.30 implementira QThread workere za background DB operacije (UI se ne zamrzava) i Alembic za schema migracije. Workeri: LoadDashboardWorker, LoadCustomersWorker, LoadOrdersWorker, LoadInstallmentsWorker, LoadPaymentsWorker, LoadCampaignsWorker, LoadCampaignProductsWorker. Svi DB upiti su na background threadovima osim kratkih write operacija.
