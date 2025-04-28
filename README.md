# Paperless-ngx Media Parser

This is a custom parser for [paperless-ngx](https://github.com/paperless-ngx/paperless-ngx) designed to handle various media file types, including audio and video, as well as other formats not natively supported or requiring specific MIME type handling.

It provides:
*   Basic text extraction from certain file types (limited to the first 5KB).
*   Thumbnail generation:
    *   For video files, it attempts to extract a frame using `moviepy` (if it is installed).
    *   For other files, it generates a dynamic thumbnail showing the file extension.
*   MIME type correction based on file extension for specific custom types.

For more information on custom parser creation in Paperless-ngx, please see the ["Making Custom Parsers"](https://docs.paperless-ngx.com/development/#making-custom-parsers) section of their development docs.

## Installation

You need to make the `paperless_media` directory available to your paperless-ngx instance and install its Python dependencies.

### Docker Installation

1.  **Mount the Parser Directory:**
    Mount the `paperless_media` directory into the paperless-ngx webserver container's custom script directory (`/usr/src/paperless/src`). Update your `docker-compose.yml` or Docker run command.

    *Example `docker-compose.yml` snippet:*
    ```yaml
    services:
      webserver:
        # ... other webserver config ...
        volumes:
          - /path/to/your/paperless_media:/usr/src/paperless/src/paperless_media
          # ... other volumes ...
    ```
    Replace `/path/to/your/paperless_media` with the actual path to the `paperless_media` directory on your host machine.

2.  Set an environment variable telling paperless to load the new extension. This can be done via 
    the docker-compose.yml or by injecting a environment variable in via portainer or another method.  
      
    *Example `docker-compose.yml` snippet:*
    ```yaml
    environment:
        PAPERLESS_APPS: paperless_media
    ```

3.  **Restart Paperless-ngx:**
    Restart your paperless-ngx stack:
    ```bash
    docker-compose down
    docker-compose up -d
    ```

### Non-Docker (Bare Metal) Installation

1.  **Copy the Parser Directory:**
    Copy the entire `paperless_media` directory into the paperless-ngx `src` directory. The location of this directory depends on your specific installation method, but it's typically within the paperless-ngx source code or installation directory.

    *Example:*
    ```bash
    cp -r /path/to/your/paperless_media /path/to/paperless-ngx/src/
    ```

2.  **Restart Paperless-ngx:**
    Restart the paperless-ngx webserver and consumer processes according to your system's service management (e.g., `systemctl restart paperless-webserver paperless-consumer`).

### Optional Video Thumbnail Creation

In order for video thumbnail generation to work properly the Python `moviepy` package must be installed. This can be accomplished in multiple ways depending on how you have installed Paperless-ngx (container, running local, etc.).

To install the required Python packages into the Python environment used by paperless-ngx. Navigate to the `paperless_media` directory and run:
```bash
# Activate your paperless virtual environment first if you use one
# source /path/to/paperless/venv/bin/activate
pip install -r requirements.txt
```

## Usage

Once installed and paperless-ngx is restarted, the media parser should be automatically detected and the previously prohibited files can now be uploaded successfully.

## Notes

*   Video thumbnail generation requires `moviepy`, which in turn depends on `ffmpeg`.  See instructions above for installing moviepy.
*   Text extraction is very basic and only reads the beginning of the file. It's primarily intended for text-based formats included in the parser's scope or as a fallback. It will likely not produce useful text from binary media files.
