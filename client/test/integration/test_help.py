def test_classification_definition(client):
    res = client.help.classification_definition()
    assert "RESTRICTED" in res
    assert "UNRESTRICTED" in res
