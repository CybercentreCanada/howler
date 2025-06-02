from howler_client.client import Client


def test_same_analytic_only(client: Client):
    assert client.hit.generate_hash(
        {"howler.analytic": "Analytic 1"}
    ) == client.hit.generate_hash({"howler.analytic": "Analytic 1"})


def test_different_analytic_only(client: Client):
    assert client.hit.generate_hash(
        {"howler.analytic": "Analytic 1"}
    ) != client.hit.generate_hash({"howler.analytic": "Analytic 2"})


def test_same_analytic_same_detection(client: Client):
    assert client.hit.generate_hash(
        {"howler.analytic": "Analytic 1", "howler.detection": "Detection 1"}
    ) == client.hit.generate_hash(
        {"howler.analytic": "Analytic 1", "howler.detection": "Detection 1"}
    )


def test_same_analytic_different_detection(client: Client):
    assert client.hit.generate_hash(
        {"howler.analytic": "Analytic 1", "howler.detection": "Detection 1"}
    ) != client.hit.generate_hash(
        {"howler.analytic": "Analytic 1", "howler.detection": "Detection 2"}
    )


def test_same_analytic_same_detection_same_single_data(client: Client):
    assert client.hit.generate_hash(
        {
            "howler.analytic": "Analytic 1",
            "howler.detection": "Detection 1",
            "howler.data": ["test"],
        }
    ) == client.hit.generate_hash(
        {
            "howler.analytic": "Analytic 1",
            "howler.detection": "Detection 1",
            "howler.data": ["test"],
        }
    )


def test_same_analytic_same_detection_different_single_data(client: Client):
    assert client.hit.generate_hash(
        {
            "howler.analytic": "Analytic 1",
            "howler.detection": "Detection 1",
            "howler.data": ["test"],
        }
    ) != client.hit.generate_hash(
        {
            "howler.analytic": "Analytic 1",
            "howler.detection": "Detection 1",
            "howler.data": ["test2"],
        }
    )


def test_same_analytic_same_detection_same_multiple_data(client: Client):
    assert client.hit.generate_hash(
        {
            "howler.analytic": "Analytic 1",
            "howler.detection": "Detection 1",
            "howler.data": ["test", "test2"],
        }
    ) == client.hit.generate_hash(
        {
            "howler.analytic": "Analytic 1",
            "howler.detection": "Detection 1",
            "howler.data": ["test", "test2"],
        }
    )


def test_same_analytic_same_detection_different_multiple_data(client: Client):
    assert client.hit.generate_hash(
        {
            "howler.analytic": "Analytic 1",
            "howler.detection": "Detection 1",
            "howler.data": ["test", "test2"],
        }
    ) != client.hit.generate_hash(
        {
            "howler.analytic": "Analytic 1",
            "howler.detection": "Detection 1",
            "howler.data": ["test", "test1"],
        }
    )


def test_same_analytic_same_detection_same_multiple_data_out_of_order(client: Client):
    assert client.hit.generate_hash(
        {
            "howler.analytic": "Analytic 1",
            "howler.detection": "Detection 1",
            "howler.data": ["test2", "test"],
        }
    ) == client.hit.generate_hash(
        {
            "howler.analytic": "Analytic 1",
            "howler.detection": "Detection 1",
            "howler.data": ["test", "test2"],
        }
    )

    assert client.hit.generate_hash(
        {
            "howler.analytic": "Analytic 1",
            "howler.detection": "Detection 1",
            "howler.data": ["test2", "test", {}, True],
        }
    ) == client.hit.generate_hash(
        {
            "howler.analytic": "Analytic 1",
            "howler.detection": "Detection 1",
            "howler.data": ["test", {}, "test2", True],
        }
    )

    assert client.hit.generate_hash(
        {
            "howler.analytic": "Analytic 1",
            "howler.detection": "Detection 1",
            "howler.data": [{"complex": "dict", "thing": []}, {}],
        }
    ) == client.hit.generate_hash(
        {
            "howler.analytic": "Analytic 1",
            "howler.detection": "Detection 1",
            "howler.data": [{}, {"thing": [], "complex": "dict"}],
        }
    )


def test_same_analytic_same_detection_with_without_data(client: Client):
    assert client.hit.generate_hash(
        {
            "howler.analytic": "Analytic 1",
            "howler.detection": "Detection 1",
            "howler.data": [],
        }
    ) != client.hit.generate_hash(
        {
            "howler.analytic": "Analytic 1",
            "howler.detection": "Detection 1",
            "howler.data": ["test"],
        }
    )

    assert client.hit.generate_hash(
        {
            "howler.analytic": "Analytic 1",
            "howler.detection": "Detection 1",
        }
    ) != client.hit.generate_hash(
        {
            "howler.analytic": "Analytic 1",
            "howler.detection": "Detection 1",
            "howler.data": ["test"],
        }
    )
