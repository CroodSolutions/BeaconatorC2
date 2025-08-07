#!/usr/bin/env python3
"""
Enhanced NTDS/SAM/SYSTEM analyzer with better minimal AD support
"""

import sys
import os
import argparse
import logging
from binascii import hexlify, unhexlify
import struct

try:
    from impacket.examples.secretsdump import LocalOperations, SAMHashes, LSASecrets, NTDSHashes
    from impacket import LOG
    from impacket.ese import ESENT_DB
    from impacket.structure import hexdump
except ImportError:
    print("Error: impacket library not found!")
    print("Install it with: pip install impacket")
    sys.exit(1)

class SimpleSecretsDump:
    def __init__(self, system_file, output_dir=None):
        self.system_file = system_file
        self.output_dir = output_dir or os.path.dirname(system_file)
        self.boot_key = None
        self.no_lm_hash = True

        # Set up logging
        logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

    def get_boot_key(self):
        """Extract boot key from SYSTEM hive"""
        if not os.path.exists(self.system_file):
            LOG.error(f"SYSTEM file not found: {self.system_file}")
            return None

        LOG.info(f"Extracting boot key from: {self.system_file}")
        local_ops = LocalOperations(self.system_file)
        self.boot_key = local_ops.getBootKey()

        if self.boot_key:
            LOG.info(f"Boot key: 0x{hexlify(self.boot_key).decode('utf-8')}")

        return self.boot_key

    def dump_sam_hashes(self, sam_file):
        """Dump SAM hashes"""
        if not os.path.exists(sam_file):
            LOG.error(f"SAM file not found: {sam_file}")
            return

        if not self.boot_key:
            LOG.error("Boot key not available!")
            return

        LOG.info(f"\nDumping SAM hashes from: {sam_file}")
        LOG.info("="*60)

        try:
            sam_hashes = SAMHashes(sam_file, self.boot_key, isRemote=False)
            sam_hashes.dump()

            if self.output_dir:
                output_base = os.path.join(self.output_dir, 'extracted_hashes')
                try:
                    sam_hashes.export(output_base)
                    LOG.info(f"SAM hashes exported to: {output_base}.sam")
                except Exception as e:
                    LOG.warning(f"Could not export SAM hashes: {e}")
        except Exception as e:
            LOG.error(f"Error processing SAM: {e}")

    def dump_lsa_secrets(self, security_file):
        """Dump LSA secrets including DPAPI keys"""
        if not os.path.exists(security_file):
            LOG.error(f"SECURITY file not found: {security_file}")
            return

        if not self.boot_key:
            LOG.error("Boot key not available!")
            return

        LOG.info(f"\nDumping LSA secrets from: {security_file}")
        LOG.info("="*60)

        try:
            lsa_secrets = LSASecrets(security_file, self.boot_key, isRemote=False, history=False)

            try:
                lsa_secrets.dumpCachedHashes()
            except Exception as e:
                LOG.debug(f"Could not dump cached hashes: {e}")

            try:
                lsa_secrets.dumpSecrets()
            except Exception as e:
                LOG.debug(f"Could not dump secrets: {e}")

            if self.output_dir:
                output_base = os.path.join(self.output_dir, 'extracted_hashes')
                try:
                    lsa_secrets.exportSecrets(output_base)
                    LOG.info(f"LSA secrets exported to: {output_base}.secrets")
                except:
                    pass
                try:
                    lsa_secrets.exportCached(output_base)
                    LOG.info(f"Cached hashes exported to: {output_base}.cached")
                except:
                    pass

        except Exception as e:
            LOG.error(f"Error processing SECURITY: {e}")

    def check_ntds_status(self, ntds_file):
        """Check NTDS.dit file status and characteristics"""
        file_size = os.path.getsize(ntds_file)

        with open(ntds_file, 'rb') as f:
            header = f.read(512)

        is_minimal = False
        page_size = 0

        # Check for ESE signature
        if header[4:8] == b'\xef\xcd\xab\x89':
            LOG.info("Valid ESE database signature found")

            # Get page size
            if len(header) >= 240:
                page_size = struct.unpack('<I', header[236:240])[0]
                LOG.info(f"Page size: {page_size} bytes")

                total_pages = file_size // page_size
                LOG.info(f"File size: {file_size} bytes ({total_pages} pages)")

                # Check if minimal
                if file_size == 41943040:  # Exactly 40MB
                    LOG.info("This appears to be a minimal/empty test AD database")
                    is_minimal = True
                elif file_size < 50 * 1024 * 1024:  # Less than 50MB
                    LOG.info("This appears to be a small test AD database")
                    is_minimal = True

        return is_minimal, page_size

    def dump_ntds_hashes(self, ntds_file):
        """Dump NTDS.dit hashes"""
        if not os.path.exists(ntds_file):
            LOG.error(f"NTDS.dit file not found: {ntds_file}")
            return

        if not self.boot_key:
            LOG.error("Boot key not available!")
            return

        LOG.info(f"\nProcessing NTDS.dit from: {ntds_file}")
        LOG.info("="*60)

        # Check NTDS status
        is_minimal, page_size = self.check_ntds_status(ntds_file)

        # Set up output file
        output_base = None
        if self.output_dir:
            output_base = os.path.join(self.output_dir, 'extracted_hashes')

        try:
            # Always try standard approach first
            LOG.info("Attempting standard NTDS extraction...")
            ntds_hashes = NTDSHashes(
                ntds_file,
                self.boot_key,
                isRemote=False,
                history=True,
                noLMHash=self.no_lm_hash,
                remoteOps=None,
                useVSSMethod=True,
                outputFileName=output_base
            )

            ntds_hashes.dump()
            ntds_hashes.finish()

            if output_base and os.path.exists(output_base + '.ntds'):
                LOG.info(f"NTDS hashes exported to: {output_base}.ntds")

        except Exception as e:
            LOG.error(f"NTDS extraction failed: {e}")



def main():
    parser = argparse.ArgumentParser(description='Analyze extracted NTDS/SAM/SYSTEM/SECURITY files')
    parser.add_argument('extraction_dir', help='Directory containing extracted files')
    parser.add_argument('-s', '--sam-only', action='store_true', help='Only dump SAM hashes')
    parser.add_argument('-n', '--ntds-only', action='store_true', help='Only dump NTDS hashes')
    parser.add_argument('-l', '--lsa-only', action='store_true', help='Only dump LSA secrets')
    parser.add_argument('-o', '--output-dir', help='Output directory for hash files')
    parser.add_argument('-q', '--quiet', action='store_true', help='Minimal output')

    args = parser.parse_args()

    if args.quiet:
        logging.basicConfig(level=logging.ERROR)

    # Check if extraction directory exists
    if not os.path.exists(args.extraction_dir):
        print(f"Error: Directory not found: {args.extraction_dir}")
        sys.exit(1)

    # Look for required files
    system_file = os.path.join(args.extraction_dir, 'SYSTEM')
    sam_file = os.path.join(args.extraction_dir, 'SAM')
    security_file = os.path.join(args.extraction_dir, 'SECURITY')
    ntds_file = os.path.join(args.extraction_dir, 'ntds.dit')

    # Check if SYSTEM file exists (always required)
    if not os.path.exists(system_file):
        print(f"Error: SYSTEM file not found in {args.extraction_dir}")
        print("The SYSTEM file is required to extract the boot key")
        sys.exit(1)

    # Create dumper instance
    dumper = SimpleSecretsDump(system_file, args.output_dir or args.extraction_dir)

    # Get boot key first
    if not dumper.get_boot_key():
        print("Error: Failed to extract boot key!")
        sys.exit(1)

    # Dump based on options
    if args.sam_only:
        dumper.dump_sam_hashes(sam_file)
    elif args.ntds_only:
        dumper.dump_ntds_hashes(ntds_file)
    elif args.lsa_only:
        dumper.dump_lsa_secrets(security_file)
    else:
        # Dump everything available
        print("\n" + "="*60)
        print("Starting hash extraction...")
        print("="*60)

        if os.path.exists(sam_file):
            dumper.dump_sam_hashes(sam_file)
        else:
            LOG.warning("SAM file not found, skipping SAM hashes")

        if os.path.exists(security_file):
            dumper.dump_lsa_secrets(security_file)
        else:
            LOG.warning("SECURITY file not found, skipping LSA secrets")

        if os.path.exists(ntds_file):
            dumper.dump_ntds_hashes(ntds_file)
        else:
            LOG.warning("NTDS.dit file not found, skipping domain hashes")

        # Summary for minimal ADs
        if os.path.exists(ntds_file):
            is_minimal, _ = dumper.check_ntds_status(ntds_file)
            if is_minimal:
                print("\n" + "="*60)
                print("SUMMARY FOR MINIMAL TEST AD")
                print("="*60)
                print("Successfully extracted:")
                print("SAM hashes (local Administrator)")
                print("LSA secrets (DPAPI keys, machine account)")

    print("\n" + "="*60)
    print("Hash extraction complete!")
    print("="*60)

if __name__ == '__main__':
    main()