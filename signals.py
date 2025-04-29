import logging

# Add necessary imports for the signal receiver
from django.db.models.signals import pre_save
from django.dispatch import receiver
from documents.models import Document
from .mime_types import PPM_MIME_TYPES
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

def _get_combined_mime_types():
    # Reads generated.mime-types and merges it with the base PPM_MIME_TYPES,
    # giving precedence to PPM_MIME_TYPES for duplicates.
    combined_mime_types = PPM_MIME_TYPES.copy()
    generated_mime_file = "generated.mime-types"
    
    try:
        script_dir = os.path.dirname(__file__)
        file_path = os.path.join(script_dir, generated_mime_file)

        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or ':' not in line or line.startswith('#'):
                        continue # Skip empty lines, lines without a colon, or comment lines

                    mime_type, extension = line.split(':', 1)
                    mime_type = mime_type.strip()
                    extension = extension.strip()

                    if mime_type and extension:
                        if not extension.startswith('.'):
                             extension = '.' + extension

                        if mime_type not in combined_mime_types:
                            combined_mime_types[mime_type] = extension

        else:
             logger.warning(f"File not found: {file_path}")

    except Exception as e:
        logger.error(f"Error reading or processing {generated_mime_file}: {e}")
        
    return combined_mime_types


def get_parser(*args, **kwargs):
    from paperless_media.parsers import MediaDocumentParser

    return MediaDocumentParser(*args, **kwargs)


def media_consumer_declaration(sender, **kwargs):
    logger.debug("media_consumer_declaration called with sender: %s, kwargs: %s", sender, kwargs)

    combined_mime_types = _get_combined_mime_types()

    return {
        "parser": get_parser,
        "weight": -1,
        "mime_types": combined_mime_types
    }

# Pre-save document handler
@receiver(pre_save, sender=Document)
def correct_mime_type_receiver(sender, instance: Document, **kwargs):
    _filename, extension = os.path.splitext(instance.original_filename)
    extension = extension.lower()

    combined_mime_types = _get_combined_mime_types()

    matched_mime = None
    for mime, ext in combined_mime_types.items():
        if extension == ext:
            matched_mime = mime
            break

    if matched_mime:
        new_mime_type = matched_mime # Use the matched MIME type

        # Only change if different from what was detected
        if instance.mime_type != new_mime_type:
            instance.mime_type = new_mime_type
    else:
        # If no mime type match was found, check if we should add it to generated.mime-types
        current_mime = instance.mime_type
        
        # Skip if it's a text or image file, or a common document format
        exclude_extensions = ['.docx', '.doc', '.odt', '.ppt', '.pptx', '.odp', '.xls', '.xlsx', '.ods']
        if (not current_mime.startswith('text/') and 
            not current_mime.startswith('image/') and 
            extension not in exclude_extensions and
            extension):  # Ensure we have a non-empty extension
            
            # Create a custom mime type based on the original mime and extension
            extension_without_dot = extension[1:] if extension.startswith('.') else extension
            custom_mime = f"{current_mime}-{extension_without_dot}"
            
            # Add to generated.mime-types file if not already there
            script_dir = os.path.dirname(__file__)
            file_path = os.path.join(script_dir, "generated.mime-types")
            
            try:
                with open(file_path, 'a+') as f:
                    f.write(f"{custom_mime}: {extension}\n")
                logger.info(f"Added new mime type to generated.mime-types: {custom_mime}: {extension}")
            except Exception as e:
                logger.error(f"Error writing to generated.mime-types: {e}")
        
            # Update the instance mime type to the custom one
            instance.mime_type = custom_mime
