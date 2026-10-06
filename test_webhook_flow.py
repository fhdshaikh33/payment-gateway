import asyncio
import logging
import sys
import uuid
import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("test_webhook_flow")

BASE_URL = "http://localhost:8000/api/v1"


async def main():
    async with httpx.AsyncClient() as client:
        # 1. Register a Merchant
        logger.info("Registering Merchant...")
        email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        reg_resp = await client.post(
            f"{BASE_URL}/merchants/register",
            json={
                "business_name": "Test Webhook Business",
                "legal_entity_type": "PVT_LTD",
                "full_name": "Test User",
                "email": email,
                "password": "Password123!",
            },
        )
        assert reg_resp.status_code == 201, f"Failed to register: {reg_resp.text}"
        logger.info("Merchant registered successfully.")

        # 2. Login
        logger.info("Logging in...")
        login_resp = await client.post(
            f"{BASE_URL}/auth/login",
            json={"email": email, "password": "Password123!"},
        )
        assert login_resp.status_code == 200, f"Failed to login: {login_resp.text}"
        access_token = login_resp.json()["data"]["access_token"]
        logger.info("Logged in successfully.")

        # 3. Generate API Key
        logger.info("Generating API Key...")
        keys_resp = await client.post(
            f"{BASE_URL}/merchants/keys/generate",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"environment": "TEST"},
        )
        assert keys_resp.status_code == 200, f"Failed to generate keys: {keys_resp.text}"
        key_data = keys_resp.json()["data"]
        key_id = key_data["key_id"]
        key_secret = key_data["key_secret"]
        logger.info("API Key generated: %s", key_id)

        # 4. Register Webhook Endpoint
        logger.info("Registering Webhook Endpoint...")
        auth = (key_id, key_secret)
        wh_resp = await client.post(
            f"{BASE_URL}/webhooks/endpoints",
            auth=auth,
            json={
                "url": "https://httpbin.org/post",
                "events": ["ping", "payment.captured", "refund.created"],
                "description": "Test Webhook",
            },
        )
        assert wh_resp.status_code == 201, f"Failed to register webhook: {wh_resp.text}"
        endpoint_id = wh_resp.json()["id"]
        logger.info("Webhook registered successfully. ID: %s", endpoint_id)

        # 5. Send Test Webhook
        logger.info("Sending Test Webhook (ping)...")
        test_resp = await client.post(
            f"{BASE_URL}/webhooks/endpoints/{endpoint_id}/test", auth=auth
        )
        assert test_resp.status_code == 202, f"Failed to send test webhook: {test_resp.text}"
        logger.info("Test Webhook dispatched.")

        # Give it a second to process the background task
        await asyncio.sleep(2)

        # 6. Check Delivery Logs
        logger.info("Checking Delivery Logs...")
        logs_resp = await client.get(
            f"{BASE_URL}/webhooks/endpoints/{endpoint_id}/deliveries", auth=auth
        )
        assert logs_resp.status_code == 200, f"Failed to fetch logs: {logs_resp.text}"
        logs = logs_resp.json()
        logger.info("Found %d delivery logs:", len(logs))
        for log in logs:
            logger.info(
                "- Event: %s, Status: %s, Response: %s",
                log["event"],
                log["status"],
                log.get("response_status"),
            )

        if logs:
            assert logs[0]["status"] == "SUCCESS", "Webhook delivery did not succeed"
            logger.info("Webhook functionality verified successfully!")
        else:
            logger.warning(
                "No delivery logs found. Background task might still be running or failed silently."
            )


if __name__ == "__main__":
    asyncio.run(main())
