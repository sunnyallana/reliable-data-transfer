import random
import time

DEBUG = True

def log(message):
    if DEBUG:
        print(f"[LOG] {message}")

class DataPacket:
    def __init__(self, sequence, content="", acknowledgment=False):
        self.sequence = sequence
        self.content = content
        self.acknowledgment = acknowledgment
        self.checksum_value = self.calculate_checksum()
    
    def calculate_checksum(self):
        total = self.sequence
        total += sum(ord(char) for char in self.content) if self.content else 0
        return total % 256
    
    def is_damaged(self):
        return self.checksum_value != self.calculate_checksum()
    
    def __str__(self):
        return f"Packet(seq={self.sequence}, data='{self.content}', ack={self.acknowledgment})"

class NetworkChannel:
    def __init__(self, loss_chance=0.3, damage_chance=0.3, delay_chance=0.2, max_delay=3):
        self.loss_chance = loss_chance
        self.damage_chance = damage_chance
        self.delay_chance = delay_chance
        self.max_delay = max_delay
        self.in_transit = []
    
    def transmit(self, packet, to_recipient):
        if random.random() < self.loss_chance:
            direction = "→ Receiver" if to_recipient else "← Sender"
            log(f"Lost {direction}: {packet}")
            return
        
        original = packet
        if random.random() < self.damage_chance:
            packet = self.modify_packet(packet)
            direction = "→ Receiver" if to_recipient else "← Sender"
            log(f"Damaged {direction}: {original} → {packet}")
        
        hold_time = 0
        if random.random() < self.delay_chance:
            hold_time = random.randint(1, self.max_delay)
            direction = "→ Receiver" if to_recipient else "← Sender"
            log(f"Delayed {direction} by {hold_time}s: {packet}")
        
        self.in_transit.append((packet, time.time() + hold_time, to_recipient))
        
        if hold_time == 0 and packet == original:
            direction = "→ Receiver" if to_recipient else "← Sender"
            log(f"Sent {direction}: {packet}")
    
    def modify_packet(self, packet):
        if packet.content:
            modified = list(packet.content)
            index = random.randint(0, len(modified)-1)
            modified[index] = chr(ord(modified[index]) + 1)
            return DataPacket(packet.sequence, "".join(modified), packet.acknowledgment)
        return packet
    
    def deliver_packets(self, current_time, for_recipient):
        delivered = []
        remaining = []
        for item in self.in_transit:
            packet, delivery_time, destination = item
            if current_time >= delivery_time and destination == for_recipient:
                delivered.append(packet)
                direction = "Received by Receiver" if for_recipient else "Received by Sender"
                log(f"{direction}: {packet}")
            else:
                remaining.append(item)
        self.in_transit = remaining
        return delivered

class ReliableSender:
    def __init__(self, channel, total_packets, packet_size=5, timeout=2):
        self.channel = channel
        self.total_packets = total_packets
        self.timeout_duration = timeout
        self.current_sequence = 0
        self.base_sequence = 0
        self.timer = None
        self.packets = [DataPacket(i%2, self.create_payload(i, packet_size)) for i in range(total_packets)]
        log(f"Sender initialized with {total_packets} packets")
    
    def create_payload(self, packet_number, size):
        return f"DATA{packet_number}-" + "X" * (size - len(f"DATA{packet_number}-"))
    
    def begin_transmission(self):
        if self.base_sequence < self.total_packets and self.timer is None:
            log(f"Starting transmission from packet {self.base_sequence}")
            self.transmit_packet(self.base_sequence)
    
    def transmit_packet(self, packet_number):
        log(f"Sending packet {packet_number}: {self.packets[packet_number].content}")
        self.channel.transmit(self.packets[packet_number], True)
        self.timer = time.time()
    
    def process_acknowledgment(self, ack_packet):
        if ack_packet.is_damaged():
            log(f"Corrupted acknowledgment received: {ack_packet}")
            return
        
        expected = self.packets[self.base_sequence].sequence
        if ack_packet.acknowledgment and ack_packet.sequence == expected:
            log(f"Valid acknowledgment for packet {self.base_sequence}")
            self.base_sequence += 1
            self.timer = None
            self.begin_transmission()
        else:
            log(f"Unexpected acknowledgment {ack_packet.sequence}, expected {expected}")
    
    def check_for_timeout(self):
        if self.timer and time.time() - self.timer > self.timeout_duration:
            log(f"Timeout for packet {self.base_sequence}, resending")
            self.transmit_packet(self.base_sequence)

class ReliableReceiver:
    def __init__(self, channel):
        self.channel = channel
        self.expected_sequence = 0
        self.received_data = []
        log("Receiver initialized")
    
    def receive_packet(self, packet):
        if packet.is_damaged():
            log(f"Damaged packet detected: {packet}")
            self.channel.transmit(DataPacket(1 - self.expected_sequence, acknowledgment=True), False)
            return
        
        log(f"Received packet {packet.sequence}, expecting {self.expected_sequence}")
        
        if packet.sequence == self.expected_sequence:
            log(f"Accepted packet: {packet.content}")
            self.received_data.append(packet.content)
            self.expected_sequence = 1 - self.expected_sequence
        
        log(f"Sending acknowledgment {packet.sequence}")
        self.channel.transmit(DataPacket(packet.sequence, acknowledgment=True), False)

class WindowedSender:
    def __init__(self, channel, total_packets, window_size=4, packet_size=5, timeout=2):
        self.channel = channel
        self.total_packets = total_packets
        self.window_size = window_size
        self.timeout_duration = timeout
        self.base_sequence = 0
        self.next_sequence = 0
        self.timer = None
        self.packets = [DataPacket(i, self.create_payload(i, packet_size)) for i in range(total_packets)]
        log(f"Windowed sender initialized with window size {window_size}")
    
    def create_payload(self, packet_number, size):
        return f"DATA{packet_number}-" + "X" * (size - len(f"DATA{packet_number}-"))
    
    def begin_transmission(self):
        log(f"Starting window transmission from {self.base_sequence}")
        while self.next_sequence < min(self.base_sequence + self.window_size, self.total_packets):
            log(f"Sending packet {self.next_sequence}")
            self.channel.transmit(self.packets[self.next_sequence], True)
            self.next_sequence += 1
        
        if self.timer is None and self.base_sequence < self.next_sequence:
            self.timer = time.time()
            log(f"Timer started for window {self.base_sequence}-{self.next_sequence-1}")
    
    def process_acknowledgment(self, ack_packet):
        if ack_packet.is_damaged():
            log(f"Corrupted acknowledgment received: {ack_packet}")
            return
        
        log(f"Received acknowledgment for {ack_packet.sequence}")
        
        if self.base_sequence <= ack_packet.sequence < self.total_packets:
            previous_base = self.base_sequence
            self.base_sequence = ack_packet.sequence + 1
            log(f"Updated window base from {previous_base} to {self.base_sequence}")
            
            if self.base_sequence == self.next_sequence:
                self.timer = None
            else:
                self.timer = time.time()
            
            self.begin_transmission()
    
    def check_for_timeout(self):
        if self.timer and time.time() - self.timer > self.timeout_duration:
            log(f"Window timeout, resending from {self.base_sequence}")
            self.next_sequence = self.base_sequence
            self.begin_transmission()

class WindowedReceiver:
    def __init__(self, channel):
        self.channel = channel
        self.expected_sequence = 0
        self.received_data = []
        log("Windowed receiver ready")
    
    def receive_packet(self, packet):
        if packet.is_damaged():
            log(f"Damaged packet detected: {packet}")
            self.channel.transmit(DataPacket(self.expected_sequence-1, acknowledgment=True), False)
            return
        
        log(f"Received packet {packet.sequence}, expecting {self.expected_sequence}")
        
        if packet.sequence == self.expected_sequence:
            log(f"Accepted packet: {packet.content}")
            self.received_data.append(packet.content)
            self.expected_sequence += 1
        
        log(f"Sending acknowledgment {self.expected_sequence-1}")
        self.channel.transmit(DataPacket(self.expected_sequence-1, acknowledgment=True), False)

class SelectiveSender:
    def __init__(self, channel, total_packets, window_size=4, packet_size=5, timeout=2):
        self.channel = channel
        self.total_packets = total_packets
        self.window_size = window_size
        self.timeout_duration = timeout
        self.base_sequence = 0
        self.acknowledged = [False] * total_packets
        self.timers = [None] * total_packets
        self.packets = [DataPacket(i, self.create_payload(i, packet_size)) for i in range(total_packets)]
        log(f"Selective sender initialized with window size {window_size}")
    
    def create_payload(self, packet_number, size):
        return f"DATA{packet_number}-" + "X" * (size - len(f"DATA{packet_number}-"))
    
    def begin_transmission(self):
        log(f"Starting selective transmission from {self.base_sequence}")
        for seq in range(self.base_sequence, min(self.base_sequence + self.window_size, self.total_packets)):
            if not self.acknowledged[seq] and self.timers[seq] is None:
                log(f"Sending packet {seq}")
                self.channel.transmit(self.packets[seq], True)
                self.timers[seq] = time.time()
    
    def process_acknowledgment(self, ack_packet):
        if ack_packet.is_damaged():
            log(f"Corrupted acknowledgment received: {ack_packet}")
            return
        
        seq_number = ack_packet.sequence
        log(f"Received acknowledgment for {seq_number}")
        
        if 0 <= seq_number < self.total_packets and not self.acknowledged[seq_number]:
            log(f"Marking packet {seq_number} as acknowledged")
            self.acknowledged[seq_number] = True
            self.timers[seq_number] = None
            
            previous_base = self.base_sequence
            while self.base_sequence < self.total_packets and self.acknowledged[self.base_sequence]:
                self.base_sequence += 1
            
            if previous_base != self.base_sequence:
                log(f"New window base: {self.base_sequence}")
            
            self.begin_transmission()
    
    def check_for_timeout(self):
        current_time = time.time()
        for seq in range(self.base_sequence, min(self.base_sequence + self.window_size, self.total_packets)):
            if not self.acknowledged[seq] and self.timers[seq] and current_time - self.timers[seq] > self.timeout_duration:
                log(f"Timeout for packet {seq}, resending")
                self.channel.transmit(self.packets[seq], True)
                self.timers[seq] = current_time

class SelectiveReceiver:
    def __init__(self, channel, window_size=4):
        self.channel = channel
        self.window_size = window_size
        self.base_sequence = 0
        self.buffer = {}
        self.received_data = []
        log(f"Selective receiver ready with window size {window_size}")
    
    def receive_packet(self, packet):
        if packet.is_damaged():
            log(f"Damaged packet detected: {packet}")
            return
        
        seq_number = packet.sequence
        log(f"Received packet {seq_number}, current base {self.base_sequence}")
        
        if self.base_sequence <= seq_number < self.base_sequence + self.window_size:
            log(f"Buffering packet {seq_number}")
            self.buffer[seq_number] = packet.content
            self.channel.transmit(DataPacket(seq_number, acknowledgment=True), False)
        elif self.base_sequence - self.window_size <= seq_number < self.base_sequence:
            self.channel.transmit(DataPacket(seq_number, acknowledgment=True), False)
        else:
            log(f"Packet {seq_number} outside current window")
        
        while self.base_sequence in self.buffer:
            self.received_data.append(self.buffer[self.base_sequence])
            del self.buffer[self.base_sequence]
            self.base_sequence += 1
            log(f"New base sequence: {self.base_sequence}")

def run_protocol(protocol_name, total=10, window=4, packet_size=5, loss=0.2, corruption=0.2, delay=0.2, max_time=30):
    network = NetworkChannel(loss_chance=loss, damage_chance=corruption, delay_chance=delay)
    
    if protocol_name == "rdt":
        transmitter = ReliableSender(network, total, packet_size)
        receiver = ReliableReceiver(network)
    elif protocol_name == "gbn":
        transmitter = WindowedSender(network, total, window, packet_size)
        receiver = WindowedReceiver(network)
    elif protocol_name == "sr":
        transmitter = SelectiveSender(network, total, window, packet_size)
        receiver = SelectiveReceiver(network, window)
    
    transmitter.begin_transmission()
    start_time = time.time()
    
    while transmitter.base_sequence < total and time.time() - start_time < max_time:
        current_time = time.time()
        
        for packet in network.deliver_packets(current_time, True):
            receiver.receive_packet(packet)
        
        for ack in network.deliver_packets(current_time, False):
            transmitter.process_acknowledgment(ack)
        
        transmitter.check_for_timeout()
        time.sleep(0.1)
    
    end_time = time.time()
    duration = end_time - start_time
    
    results = {
        "protocol": protocol_name,
        "total_packets": total,
        "received_packets": len(receiver.received_data),
        "duration": duration,
        "success_rate": len(receiver.received_data) / total if total > 0 else 0,
        "timeout_occurred": transmitter.base_sequence < total
    }
    
    log(f"\nCompleted {protocol_name.upper()} simulation")
    log(f"Duration: {duration:.2f} seconds")
    log(f"Success rate: {results['success_rate'] * 100:.1f}%")
    
    return receiver.received_data, results

def execute_test_cases():
    print("\nBasic Functionality Test")
    for protocol in ["rdt", "gbn", "sr"]:
        data, _ = run_protocol(protocol, total=5)
        print(f"{protocol.upper()} Results: {data}")

if __name__ == "__main__":
    DEBUG = True
    execute_test_cases()
