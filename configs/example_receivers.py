"""
Example receiver configurations for testing the new receiver architecture.
This file demonstrates how to create different types of receivers with various encoding strategies.
"""

from services.receivers import ReceiverConfig, ReceiverType

def create_example_receivers():
    """Create example receiver configurations for testing"""
    
    # Basic TCP receiver with plain text
    tcp_plain = ReceiverConfig(
        name="TCP Plain Text",
        receiver_type=ReceiverType.TCP,
        enabled=True,
        auto_start=False,
        host="0.0.0.0",
        port=5075,
        encoding_type="plain",
        description="Basic TCP receiver without encoding"
    )
    
    # TCP receiver with Base64 encoding
    tcp_base64 = ReceiverConfig(
        name="TCP Base64",
        receiver_type=ReceiverType.TCP,
        enabled=True,
        auto_start=False,
        host="0.0.0.0",
        port=5076,
        encoding_type="base64",
        description="TCP receiver with Base64 encoding"
    )
    
    # TCP receiver with XOR encoding
    tcp_xor = ReceiverConfig(
        name="TCP XOR Encoded",
        receiver_type=ReceiverType.TCP,
        enabled=True,
        auto_start=False,
        host="0.0.0.0",
        port=5077,
        encoding_type="xor",
        encoding_config={"key": "supersecretkey123"},
        description="TCP receiver with XOR encoding"
    )
    
    # TCP receiver with ROT encoding
    tcp_rot = ReceiverConfig(
        name="TCP ROT13",
        receiver_type=ReceiverType.TCP,
        enabled=True,
        auto_start=False,
        host="0.0.0.0",
        port=5078,
        encoding_type="rot",
        encoding_config={"shift": 13},
        description="TCP receiver with ROT13 encoding"
    )
    
    # High-performance TCP receiver
    tcp_performance = ReceiverConfig(
        name="TCP High Performance",
        receiver_type=ReceiverType.TCP,
        enabled=True,
        auto_start=False,
        host="0.0.0.0",
        port=5079,
        encoding_type="plain",
        buffer_size=2097152,  # 2MB buffer
        max_connections=200,
        description="High-performance TCP receiver with large buffers"
    )
    
    return [tcp_plain, tcp_base64, tcp_xor, tcp_rot, tcp_performance]

def load_example_receivers_to_manager(receiver_manager):
    """Load example receivers into a receiver manager"""
    examples = create_example_receivers()
    
    for config in examples:
        try:
            receiver_manager.create_receiver(config)
            print(f"Created example receiver: {config.name}")
        except Exception as e:
            print(f"Failed to create receiver {config.name}: {e}")
    
    print(f"Loaded {len(examples)} example receivers")

if __name__ == "__main__":
    # Example usage
    from services.receivers import ReceiverManager
    
    manager = ReceiverManager()
    load_example_receivers_to_manager(manager)
    
    print("\nReceiver Summary:")
    summary = manager.get_receiver_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")