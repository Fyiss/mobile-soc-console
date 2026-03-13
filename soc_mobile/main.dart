import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

void main() {
  runApp(const SOCApp());
}

// ─── Models ───────────────────────────────────────────────────────────────────

class Alert {
  final String id;
  final String type;
  final String severity;
  final String sourceIp;
  final int pid;
  final String description;
  final String timestamp;
  bool dismissed;

  Alert({
    required this.id,
    required this.type,
    required this.severity,
    required this.sourceIp,
    required this.pid,
    required this.description,
    required this.timestamp,
    this.dismissed = false,
  });

  factory Alert.fromJson(Map<String, dynamic> j) => Alert(
        id: j['id'] ?? '',
        type: j['type'] ?? '',
        severity: j['severity'] ?? 'low',
        sourceIp: j['source_ip'] ?? '',
        pid: j['pid'] ?? 0,
        description: j['description'] ?? '',
        timestamp: j['timestamp'] ?? '',
      );

  Color get severityColor {
    switch (severity) {
      case 'critical':
        return const Color(0xFFFF3B30);
      case 'high':
        return const Color(0xFFFF9500);
      case 'medium':
        return const Color(0xFFFFCC00);
      default:
        return const Color(0xFF34C759);
    }
  }

  IconData get icon {
    if (type.contains('ssh')) return Icons.terminal;
    if (type.contains('process')) return Icons.memory;
    if (type.contains('network') || type.contains('port')) return Icons.wifi;
    if (type.contains('log')) return Icons.article;
    return Icons.warning_amber;
  }
}

// ─── App ──────────────────────────────────────────────────────────────────────

class SOCApp extends StatelessWidget {
  const SOCApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SOC Console',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF0A0A0F),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF00D4FF),
          surface: Color(0xFF12121A),
        ),
        cardTheme: CardTheme(
          color: const Color(0xFF12121A),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          elevation: 0,
        ),
      ),
      home: const AuthGate(),
    );
  }
}

// ─── Auth Gate ────────────────────────────────────────────────────────────────

class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  @override
  void initState() {
    super.initState();
    _check();
  }

  Future<void> _check() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('token');
    if (token != null && mounted) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const DashboardScreen()),
      );
    }
  }

  @override
  Widget build(BuildContext context) => const LoginScreen();
}

// ─── Login ────────────────────────────────────────────────────────────────────

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _hostCtrl = TextEditingController(text: 'http://192.168.1.100:8000');
  final _userCtrl = TextEditingController(text: 'admin');
  final _passCtrl = TextEditingController(text: 'soc-password-123');
  bool _loading = false;
  String? _error;

  Future<void> _login() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final res = await http.post(
        Uri.parse('${_hostCtrl.text}/auth/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'username': _userCtrl.text,
          'password': _passCtrl.text,
        }),
      ).timeout(const Duration(seconds: 10));

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('token', data['access_token']);
        await prefs.setString('host', _hostCtrl.text);

        if (mounted) {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(builder: (_) => const DashboardScreen()),
          );
        }
      } else {
        setState(() => _error = 'Invalid credentials');
      }
    } catch (e) {
      setState(() => _error = 'Cannot reach broker: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.shield, color: Color(0xFF00D4FF), size: 48),
              const SizedBox(height: 16),
              const Text('SOC Console',
                  style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold)),
              const Text('Mobile Incident Response',
                  style: TextStyle(color: Colors.white54)),
              const SizedBox(height: 48),
              _field(_hostCtrl, 'Broker URL', Icons.cloud),
              const SizedBox(height: 16),
              _field(_userCtrl, 'Username', Icons.person),
              const SizedBox(height: 16),
              _field(_passCtrl, 'Password', Icons.lock, obscure: true),
              if (_error != null) ...[
                const SizedBox(height: 16),
                Text(_error!, style: const TextStyle(color: Color(0xFFFF3B30))),
              ],
              const SizedBox(height: 32),
              SizedBox(
                width: double.infinity,
                height: 52,
                child: ElevatedButton(
                  onPressed: _loading ? null : _login,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF00D4FF),
                    foregroundColor: Colors.black,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12)),
                  ),
                  child: _loading
                      ? const CircularProgressIndicator(color: Colors.black)
                      : const Text('Connect',
                          style: TextStyle(
                              fontSize: 16, fontWeight: FontWeight.bold)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _field(TextEditingController ctrl, String label, IconData icon,
      {bool obscure = false}) {
    return TextField(
      controller: ctrl,
      obscureText: obscure,
      style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon, color: const Color(0xFF00D4FF)),
        filled: true,
        fillColor: const Color(0xFF12121A),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        labelStyle: const TextStyle(color: Colors.white54),
      ),
    );
  }
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final List<Alert> _alerts = [];
  WebSocketChannel? _channel;
  bool _connected = false;
  String _token = '';
  String _host = '';

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString('token') ?? '';
    _host = prefs.getString('host') ?? '';
    _connectWS();
  }

  void _connectWS() {
    final wsHost = _host.replaceFirst('http://', 'ws://');
    final uri = Uri.parse('$wsHost/ws/mobile-phone?token=$_token');

    try {
      _channel = WebSocketChannel.connect(uri);
      setState(() => _connected = true);

      _channel!.stream.listen(
        (data) {
          try {
            final json = jsonDecode(data);
            final alert = Alert.fromJson(json);
            setState(() => _alerts.insert(0, alert));
          } catch (_) {}
        },
        onDone: () {
          setState(() => _connected = false);
          // Reconnect after 3s
          Future.delayed(const Duration(seconds: 3), _connectWS);
        },
        onError: (_) {
          setState(() => _connected = false);
          Future.delayed(const Duration(seconds: 3), _connectWS);
        },
      );
    } catch (e) {
      setState(() => _connected = false);
      Future.delayed(const Duration(seconds: 3), _connectWS);
    }
  }

  Future<void> _sendCommand(
      String action, String target, String eventId) async {
    try {
      final res = await http.post(
        Uri.parse('$_host/commands/send'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $_token',
        },
        body: jsonEncode({
          'action': action,
          'target': target,
          'event_id': eventId,
        }),
      ).timeout(const Duration(seconds: 10));

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(res.statusCode == 200
              ? '✓ $action executed'
              : '✗ Failed: ${res.body}'),
          backgroundColor:
              res.statusCode == 200 ? const Color(0xFF34C759) : const Color(0xFFFF3B30),
        ));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('✗ Error: $e'),
          backgroundColor: const Color(0xFFFF3B30),
        ));
      }
    }
  }

  void _showActions(Alert alert) {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF12121A),
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (_) => Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(alert.type.toUpperCase(),
                style: const TextStyle(
                    color: Colors.white54,
                    fontSize: 12,
                    letterSpacing: 1.5)),
            const SizedBox(height: 4),
            Text(alert.description,
                style: const TextStyle(
                    fontSize: 15, fontWeight: FontWeight.w500)),
            const SizedBox(height: 24),
            if (alert.sourceIp.isNotEmpty) ...[
              _actionBtn(
                Icons.block,
                'Block IP ${alert.sourceIp}',
                const Color(0xFFFF3B30),
                () {
                  Navigator.pop(context);
                  _sendCommand('block_ip', alert.sourceIp, alert.id);
                },
              ),
              const SizedBox(height: 12),
            ],
            if (alert.pid > 0) ...[
              _actionBtn(
                Icons.stop_circle,
                'Kill Process (PID ${alert.pid})',
                const Color(0xFFFF9500),
                () {
                  Navigator.pop(context);
                  _sendCommand(
                      'kill_process', alert.pid.toString(), alert.id);
                },
              ),
              const SizedBox(height: 12),
            ],
            _actionBtn(
              Icons.lock,
              'Isolate Host',
              const Color(0xFF9B59B6),
              () {
                Navigator.pop(context);
                _sendCommand('isolate', '', alert.id);
              },
            ),
            const SizedBox(height: 12),
            _actionBtn(
              Icons.check_circle,
              'Dismiss',
              const Color(0xFF34C759),
              () {
                Navigator.pop(context);
                _sendCommand('dismiss', '', alert.id);
                setState(() => alert.dismissed = true);
              },
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  Widget _actionBtn(
      IconData icon, String label, Color color, VoidCallback onTap) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        icon: Icon(icon, size: 18),
        label: Text(label),
        onPressed: onTap,
        style: ElevatedButton.styleFrom(
          backgroundColor: color.withOpacity(0.15),
          foregroundColor: color,
          padding: const EdgeInsets.symmetric(vertical: 14),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          side: BorderSide(color: color.withOpacity(0.3)),
          elevation: 0,
        ),
      ),
    );
  }

  Future<void> _logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
    _channel?.sink.close();
    if (mounted) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const LoginScreen()),
      );
    }
  }

  @override
  void dispose() {
    _channel?.sink.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final active = _alerts.where((a) => !a.dismissed).length;

    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(0xFF0A0A0F),
        elevation: 0,
        title: Row(
          children: [
            const Icon(Icons.shield, color: Color(0xFF00D4FF), size: 20),
            const SizedBox(width: 8),
            const Text('SOC Console',
                style: TextStyle(fontWeight: FontWeight.bold)),
          ],
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: Row(
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: _connected
                        ? const Color(0xFF34C759)
                        : const Color(0xFFFF3B30),
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 6),
                Text(_connected ? 'Live' : 'Offline',
                    style: TextStyle(
                        color: _connected
                            ? const Color(0xFF34C759)
                            : const Color(0xFFFF3B30),
                        fontSize: 12)),
              ],
            ),
          ),
          IconButton(
              icon: const Icon(Icons.logout, size: 20),
              onPressed: _logout),
        ],
      ),
      body: Column(
        children: [
          // Stats bar
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            color: const Color(0xFF12121A),
            child: Row(
              children: [
                _stat('Total', _alerts.length.toString(), Colors.white54),
                const SizedBox(width: 24),
                _stat('Active', active.toString(), const Color(0xFFFF3B30)),
                const SizedBox(width: 24),
                _stat(
                    'Critical',
                    _alerts
                        .where((a) =>
                            a.severity == 'critical' && !a.dismissed)
                        .length
                        .toString(),
                    const Color(0xFFFF3B30)),
                const Spacer(),
                if (_alerts.isNotEmpty)
                  TextButton(
                    onPressed: () => setState(() => _alerts.clear()),
                    child: const Text('Clear',
                        style: TextStyle(color: Colors.white38, fontSize: 12)),
                  ),
              ],
            ),
          ),
          // Alert list
          Expanded(
            child: _alerts.isEmpty
                ? Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.security,
                            size: 64,
                            color: Colors.white.withOpacity(0.1)),
                        const SizedBox(height: 16),
                        Text(
                          _connected
                              ? 'Monitoring — no alerts'
                              : 'Connecting...',
                          style: const TextStyle(color: Colors.white38),
                        ),
                      ],
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(12),
                    itemCount: _alerts.length,
                    itemBuilder: (_, i) => _alertCard(_alerts[i]),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _stat(String label, String value, Color color) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(value,
            style: TextStyle(
                color: color, fontSize: 20, fontWeight: FontWeight.bold)),
        Text(label,
            style: const TextStyle(color: Colors.white38, fontSize: 11)),
      ],
    );
  }

  Widget _alertCard(Alert alert) {
    return Opacity(
      opacity: alert.dismissed ? 0.4 : 1.0,
      child: Card(
        margin: const EdgeInsets.only(bottom: 8),
        child: InkWell(
          onTap: alert.dismissed ? null : () => _showActions(alert),
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: alert.severityColor.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(alert.icon,
                      color: alert.severityColor, size: 20),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: alert.severityColor.withOpacity(0.15),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              alert.severity.toUpperCase(),
                              style: TextStyle(
                                  color: alert.severityColor,
                                  fontSize: 9,
                                  fontWeight: FontWeight.bold,
                                  letterSpacing: 1),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              alert.type.replaceAll('_', ' '),
                              style: const TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                  color: Colors.white70),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        alert.description,
                        style: const TextStyle(
                            fontSize: 12, color: Colors.white54),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      if (alert.sourceIp.isNotEmpty) ...[
                        const SizedBox(height: 4),
                        Text('IP: ${alert.sourceIp}',
                            style: const TextStyle(
                                fontSize: 11,
                                color: Color(0xFF00D4FF),
                                fontFamily: 'monospace')),
                      ],
                    ],
                  ),
                ),
                if (!alert.dismissed)
                  const Icon(Icons.chevron_right,
                      color: Colors.white24, size: 20),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
