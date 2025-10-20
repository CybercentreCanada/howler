# Example Ingestion Using Atomic Red Team

This article will outline a very basic example of how to ingest hits into Howler, using [Atomic Red Team](https://github.com/redcanaryco/atomic-red-team) to simulate
Binary padding of a malicious file
([T1027.001](https://github.com/redcanaryco/atomic-red-team/blob/master/atomics/T1027.001/T1027.001.md)).

## Preparing a Docker Container

In order to run Atomic Red Team and detect the resulting files, we'll need to slightly modify the docker file, to
install python 3.9. First, create a new folder to include the Dockerfile and dependent files in:

```shell
mkdir -p ~/atomic-red-team-custom

# This is the test file we'll use to run the detection
echo "Hello, world\!" > test.txt

touch Dockerfile
touch detection.py
```

Put the following into the Dockerfile:

```docker
FROM redcanary/invoke-atomicredteam:latest

RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update

RUN bash -c "DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get -y install tzdata" && \
    apt-get install -y python3.9 python3.9-distutils python3.9-venv


RUN python3.9 -m ensurepip

RUN python3.9 -m pip install howler-client==1.6.0.dev16137

COPY detection.py /root/detection.py
COPY test.txt /root/test.txt
COPY test.txt /root/test_control.txt

WORKDIR /root
```

And this script into `detection.py`:

```python
import sys
import hashlib

from howler_client import get_client

USERPASS = ('<USERNAME_HERE>', '<PASSWORD>')

howler = get_client("<HOWLER_URL_HERE>", auth=APIKEY)
sha256 = hashlib.sha256()

with open("test_control.txt", "rb") as f:
    while True:
        data = f.read(65536)
        if not data:
            break

        sha256.update(data)

control_hash = sha256.hexdigest()
print(f"Control hash value: {control_hash}")

sha256 = hashlib.sha256()
with open("test.txt", "rb") as f:
    while True:
        data = f.read(65536)
        if not data:
            break

        sha256.update(data)

padded_hash = sha256.hexdigest()
print(f"Padded hash value: {padded_hash}")

if padded_hash != control_hash:
    print("Binary padding detected! Creating alert")

    howler.hit.create(
        {
            "howler.analytic": "ATR Ingestion Example",
            "howler.detection": "Binary Padding",
            "howler.score": 0,
            "threat.technique.id": "T1027.001",
            "threat.technique.name": "Obfuscated Files or Information: Binary Padding",
            "threat.technique.reference": "https://attack.mitre.org/techniques/T1027/001/",
            "related.hash": [control_hash, padded_hash],
        }
    )
else:
    print("Binary padding not detected")

```

For information on creating an API Key, see [Generating an API Key](/howler-docs/ingestion/key_generation/). The API key
should have Read and Write permissions.

## Building and Running the Docker Container

Now, you can run `docker build`:

```shell
docker build -t invoke-atomicredteam-custom:latest .
docker run --name test-howler-ingestion -it invoke-atomicredteam-custom:latest
```

After running this, you should see:

```text
PowerShell 7.4.0
Loading personal and system profiles took 700ms.
PS />
```

## Executing the Detection

If you run the detection file:

```text
PS /root> python3.9 ./detection.py
Control hash value: d9014c4624844aa5bac314773d6b689ad467fa4e1d1a50a1b8a99d5a95f72ff5
Padded hash value: d9014c4624844aa5bac314773d6b689ad467fa4e1d1a50a1b8a99d5a95f72ff5
Binary padding not detected
```

Now, we can run the atomic test:

```powershell
Invoke-AtomicTest T1027.001-1 -PromptForInputArgs
```

You should be prompted like so:

```text
Enter a value for file_to_pad, or press enter to accept the default.
Path of binary to be padded [/tmp/evil-binary]:
```

Enter the path to the test file, and run. Now, rerunning the detection:

```text
Control hash value: d9014c4624844aa5bac314773d6b689ad467fa4e1d1a50a1b8a99d5a95f72ff5
Padded hash value: ea0283ed5c7d578fe229ca383def3d08c8d2bebb164671371ecb35279993be5e
Binary padding detected! Creating alert
```

If you check your howler instance, you should now see a new alert!

??? tip "Note on Reused Alerts"
    One caveat is that, if a hit is identical each time (like the above alert), the howler client will automatically
    reuse that alert. To circumvent this, simply add a random/custom `howler.hash` field.

## Conclusion

You've now created an extremely basic script that checks two files for mismatching hashes. In reality, you'd want to run
heuristics to see if these files are similar and THEN alert, but this is more to illustrate a use case of Howler, and
the basic process of ingestion.
