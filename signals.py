import logging

# Add necessary imports for the signal receiver
from django.db.models.signals import pre_save
from django.dispatch import receiver
from documents.models import Document
import os

logger = logging.getLogger("paperless_media")

############################################################################
# DEVELOPMENT NOTES
############################################################################
#
# paperless-ngx stores files based on mime type instead of file extension.
# This particularly comes into play when you try to download/retrieve a
# file later from paperless. For example, if you register the mime type
# application/octet-stream then storage will work but the following issue
# will occur:
#
# - If you use a single file extension when configuring the mime type, like:
#   "application/octet-stream": ".afdesign"
#   If you upload a file called myfile.afphoto, the file will be stored
#   as myfile.afdesign and when you download it, it will download with the
#   wrong extension.
#
# So as a workaround we will register extensions using valid mime types when
# possible, like "video/mp4": ".mp4". However, when there isn't a mime type
# for a file - or if the same mime type applies to multiple extensions
# (e.g. yaml vs yml) - then we create a new mime type just for that extension.
# The pre-save handler @receiver in this file activates whenever a file is
# being saved. It juggles the mime types and saves the newly created one.
#
# For example: if you upload an Affinity Designer file called
# mydesign.afdesign, it will be received with a mime type of
# application/octet-stream. The pre-save handler checks the file and finds
# that it needs a custom mime type, so it saves it in the database with a
# mime type of "application/x-affinity-designer". This causes paperless-ngx
# to assign the correct file extension when you download it later. Since
# application/x-affinity-designer isn't a known mime type to web browsers,
# it will treat it as a application/octet-stream and save it properly.
#
############################################################################
#
# CLIFF NOTES:
# This plugin has to juggle mime types, and some times use fake mime type
# strings, in order to make paperless-ngx store the file properly and more
# importantly... serve it back up properly later.
# 
# If a file type has mutliple file extensions, like .yaml vs .yml, an entry
# will need to be added for the real mime type (application/yaml) for one of
# the file extensions (e.g. .yaml), and then a fake mime type added for the
# other file extension (e.g. applicaton/yml = .yml). This will allow both
# file extensions to be saved and served up by paperless.
#
# If a file type falls under the mime-type of application/octet-stream, then
# a fake mime type needs to be added with its file extension, otherwise the
# file will be saved with no extension and served back up without an ext.
#
############################################################################

# Keys must be unique, and one line per file extension type
# The mime-type has to exist in the key for paperless-ngx to allow the
# upload, but the file extension listed highest in this list will be the
# one used when saving the file (so you can allow the upload by having the
# mime type, but then override the mime-type by listing a different one
# higher in the list; see the .yaml and .yml entries)
OUR_MIME_TYPES = {
    # Text formats
    "text/xml": ".xml",
    "text/yaml": ".yaml",
    "text/yml": ".yml",
    "text/ini": ".ini",
    "text/x-sql-dump": ".sqldump",
    "text/x-sql-dump-file": ".dump",
    "text/x-sql": ".sql",
    "text/json": ".json",

    # Programming files
    "text/html": ".html",
    "text/htm": ".htm",
    "text/css": ".css",
    "application/x-perl": ".pl",
    "application/x-php": ".php",
    "application/x-httpd-php": ".php",
    "text/x-python": ".py",
    "application/x-python-code": ".py",
    "text/javascript": ".js",

    # Audio formats
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/ogg": ".ogg",
    "audio/aac": ".aac",
    "audio/midi": ".midi",
    "audio/x-mpeg": ".mp3",
    "audio/x-ms-wma": ".wma",
    "audio/x-wav": ".wav",

    # Video formats
    "video/mp4": ".mp4",
    "video/mpeg": ".mpg",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "video/quicktime-qt": ".qt",
    "video/avi": ".avi",
    "video/x-msvideo": ".avi",
    "video/x-ms-wmv": ".wmv",
    "video/x-ms-wmx": ".wmx",

    # Archive formats
    "application/zip": ".zip",
    "application/x-zip": ".zip",
    "application/x-rar-compressed": ".rar",
    "application/x-7z-compressed": ".7z",
    "application/x-tar": ".tar",
    "application/gzip": ".gz",
    "application/x-sea": ".sea",
    "application/x-sit": ".sit",

    # Document formats (additional to native support)
    "application/rtf": ".rtf",
    "application/x-latex": ".tex",
    "application/json": ".json",
    "application/yaml": ".yaml",
    "application/x-yaml": ".yaml",
    "application/xml": ".xml",

    # Presentation and publication formats
    "application/epub+zip": ".epub",

    # Photoshop formats
    "image/vnd.adobe.photoshop": ".psd",
    "application/x-photoshop": ".psd",
    "application/postscript": ".eps",

    # Executables
    "application/x-msdownload": ".exe",

    # Other formats
    "application/octet-stream": "",
    
    # application/octet-stream custom handling
    "application/x-affinity-designer": ".afdesign",
    "application/x-affinity-photo": ".afphoto",
    "application/x-affinity-publisher": ".afpub",
    "application/x-affinity-template": ".aftemplate",
    "application/x-mac-dmg": ".dmg",
    "application/postscript-ps": ".ps",
    "application/postscript-ai": ".ai",
}

def get_parser(*args, **kwargs):
    from paperless_media.parsers import MediaDocumentParser

    return MediaDocumentParser(*args, **kwargs)


def media_consumer_declaration(sender, **kwargs):
    logger.debug("media_consumer_declaration called with sender: %s, kwargs: %s", sender, kwargs)

    return {
        "parser": get_parser,
        "weight": 10,
        "mime_types": OUR_MIME_TYPES
    }

# Pre-save document handler
@receiver(pre_save, sender=Document)
def correct_mime_type_receiver(sender, instance: Document, **kwargs):
    _filename, extension = os.path.splitext(instance.original_filename)
    extension = extension.lower()

    # Use the external dictionary for checks if needed
    # Example: Check if the extension matches one in our custom list
    matched_mime = None
    for mime, ext in OUR_MIME_TYPES.items():
        if extension == ext:
            matched_mime = mime
            break

    if matched_mime:
        new_mime_type = matched_mime # Use the matched MIME type

        # Only change if different from what was detected
        if instance.mime_type != new_mime_type:
            instance.mime_type = new_mime_type
