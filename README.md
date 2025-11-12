# Rezka Downloader CLI

A small command-line tool to download films and series from Rezka (rezka.ag). It supports optional login for premium access and can download single items or whole series pages.

## Table of Contents
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Examples](#examples)
- [Configuration & Login](#configuration--login)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)

## Features
- Download films and series pages from rezka.ag
- Optional login for premium content (higher quality)
- Simple single-command usage

## Requirements
- Python 3.8+ if you plan to run from source
- (Optional) prebuilt binary for your OS (see Releases)

If running from source, install dependencies:

```zsh
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Installation

Recommended: download a prebuilt binary from the Releases page.

1. Visit the Releases page for this repository and download the appropriate binary for your platform.
2. Make the binary executable (macOS / Linux):

```zsh
chmod +x /path/to/rezka
```

3. Move it to a directory on your PATH (optional, but convenient):

```zsh
sudo mv /path/to/rezka /usr/local/bin/
```

Or run from source using `python rezka.py` after installing requirements (see above).

## Usage

Basic usage:

```zsh
rezka <URL>
```

## Examples

Download a film page:

```zsh
rezka https://rezka.ag/films/fiction/981-matrica-1999-latest.html
```

Download a series page (download behavior depends on implementation — check --help for episode selection flags):

```zsh
rezka https://rezka.ag/series/your-series-page
```

## Configuration & Login

Logging in is optional but recommended for access to premium/higher-quality streams.

To login:

```zsh
rezka login
```

This command should prompt for credentials or run an interactive flow. Login is persistent — you only need to do it once. (If you'd like, I can extract and document exactly where credentials/cookies are stored by inspecting the code.)

## Troubleshooting

- Permission denied when running the binary: ensure it is executable (`chmod +x`) and on your PATH.
- Login failures: verify credentials, network connectivity, and whether the site changed its authentication flow. Try logging in via a browser and inspect cookies if necessary.
- Downloads hang or fail: try a different quality or ensure network access to rezka.ag. If the site blocks requests, using an active session (login) may help.

If you hit an error, please open an issue with the command you ran and a short copy of the error output.

## Contributing

Contributions are welcome. Please open an issue for discussion before submitting a non-trivial change. Small fixes (typos, docs) can be sent as PRs directly.

## License

This project is licensed under the MIT License — see the `LICENSE` file for details.

## Acknowledgements

Special thanks to SuperZombi for providing a convenient API used by this project.

GitHub: https://github.com/SuperZombi/HdRezkaApi
