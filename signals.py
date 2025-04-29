import logging

# Add necessary imports for the signal receiver
from django.db.models.signals import pre_save
from django.dispatch import receiver
from documents.models import Document
from .mime_types import PPM_MIME_TYPES
import os

logger = logging.getLogger("paperless_media")

############################################################################
# FILE EXTENSION & MIME TYPE HANDLING
############################################################################
#
# ISSUE: paperless-ngx uses mime types (not file extensions) for storage.
# This creates problems when downloading files later.
#
# PROBLEM EXAMPLE:
# If you configure "application/octet-stream": ".afdesign" and upload 
# myfile.afphoto, it will be stored and downloaded as myfile.afdesign.
#
# SOLUTION:
# 1. For standard file types: Use proper mime types when possible
#    Example: "video/mp4": ".mp4"
#
# 2. For files with multiple extensions (yaml/yml): 
#    - Use real mime type for one extension: "application/yaml": ".yaml"
#    - Create custom mime type for others: "application/yml": ".yml"
#
# 3. For generic mime types (application/octet-stream):
#    - Create custom mime types for each extension
#    - Example: "application/x-affinity-designer": ".afdesign"
#
# HOW IT WORKS:
# The pre-save handler (@receiver) intercepts file saves and:
#   - Determines the file's extension
#   - Assigns the appropriate mime type from our mapping
#   - For unknown extensions, creates and records new custom mime types
#
# This ensures files download later with their correct extensions.
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
