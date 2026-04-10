from locust import HttpUser, between, task


class OnePayUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def view_dashboard(self):
        self.client.get("/dashboard")

    @task(3)
    def check_status(self):
        self.client.get("/api/payments/status?tx_ref=TEST-REF")

    @task
    def create_payment_link(self):
        self.client.post("/api/payments/link", json={
            "amount": "1000.00",
            "currency": "NGN"
        })
