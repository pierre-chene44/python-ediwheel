from datetime import datetime, timedelta
from unittest import TestCase
from unittest.mock import patch

from ediwheel.connector import EdiConnector, EdiConnectorConfig


class ResponseStub:
    def __init__(self, content, status_code=200):
        self.content = content.encode("utf-8")
        self.status_code = status_code


class BatchInquiryTests(TestCase):
    def setUp(self):
        self.config = EdiConnectorConfig(
            host="https://supplier.example.test/api",
            username="user",
            password="pass",
            id="buyer-id",
            timeout_s=3,
            max_value=25,
        )
        self.connector = EdiConnector(self.config)

    def build_response_xml(self, *lines):
        order_lines = []
        for quantity, delivery_date in lines:
            order_lines.append(
                f"""
              <OrderLine>
                <RequestedQuantity><QuantityValue>{self.config.max_value}</QuantityValue></RequestedQuantity>
                <ConfirmedQuantity><QuantityValue>{quantity}</QuantityValue></ConfirmedQuantity>
                <DeliveryDate>{delivery_date}</DeliveryDate>
              </OrderLine>"""
            )
        return "<response>" + "".join(order_lines) + "\n</response>"

    @patch("ediwheel.connector.requests.post")
    def test_batch_inquiry_renders_sequential_zero_padded_line_ids(self, post_mock):
        post_mock.return_value = ResponseStub(
            self.build_response_xml(
                (4, "2026-04-12"),
                (9, "2026-04-13"),
                (2, "2026-04-14"),
            )
        )

        self.connector.batch_inquiry(
            ["ean-1", "ean-2", "ean-3"],
            ["supplier-1", "supplier-2", "supplier-3"],
        )

        payload = post_mock.call_args.kwargs["data"]
        self.assertIn("<LineID>000001</LineID>", payload)
        self.assertIn("<LineID>000002</LineID>", payload)
        self.assertIn("<LineID>000003</LineID>", payload)
        self.assertEqual(payload.count("<OrderLine>"), 3)

    @patch("ediwheel.connector.requests.post")
    def test_batch_inquiry_returns_results_aligned_with_input_eans(self, post_mock):
        delivery_date_1 = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        delivery_date_2 = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        post_mock.return_value = ResponseStub(
            self.build_response_xml(
                (7, delivery_date_1),
                (11, delivery_date_2),
            )
        )

        result = self.connector.batch_inquiry(
            ["ean-1", "ean-2"],
            ["supplier-1", "supplier-2"],
        )

        self.assertEqual(result[0][0], "ean-1")
        self.assertEqual(result[0][1], 7)
        self.assertEqual(result[0][2], datetime.strptime(delivery_date_1, "%Y-%m-%d"))
        self.assertEqual(result[1][0], "ean-2")
        self.assertEqual(result[1][1], 11)
        self.assertEqual(result[1][2], datetime.strptime(delivery_date_2, "%Y-%m-%d"))

    @patch("ediwheel.connector.requests.post")
    def test_batch_inquiry_falls_back_to_zeroed_results_on_invalid_xml(self, post_mock):
        post_mock.return_value = ResponseStub("<response>")

        result = self.connector.batch_inquiry(
            ["ean-1", "ean-2"],
            ["supplier-1", "supplier-2"],
        )

        self.assertEqual(result, [("ean-1", 0, None), ("ean-2", 0, None)])
