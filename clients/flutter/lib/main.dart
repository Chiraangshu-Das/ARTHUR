import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:speech_to_text/speech_to_text.dart' as stt;
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

void main() => runApp(const VisionGuideMobileApp());

class VisionGuideMobileApp extends StatelessWidget {
  const VisionGuideMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'VisionGuideAI',
      theme: ThemeData(colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff23815e)), useMaterial3: true),
      home: const CommandHomePage(),
    );
  }
}

class CommandHomePage extends StatefulWidget {
  const CommandHomePage({super.key});

  @override
  State<CommandHomePage> createState() => _CommandHomePageState();
}

class _CommandHomePageState extends State<CommandHomePage> {
  final _server = TextEditingController(text: 'http://192.168.1.10:8000');
  final _token = TextEditingController();
  final _command = TextEditingController();
  final _deviceId = 'visionguide-mobile';
  final _speech = stt.SpeechToText();
  final _recorder = AudioRecorder();
  final List<String> _events = [];
  WebSocketChannel? _channel;
  StreamSubscription? _eventSubscription;
  bool _busy = false;
  bool _listening = false;
  bool _whisperRecording = false;
  String _status = 'Not connected';

  Uri _uri(String path) {
    final base = Uri.parse(_server.text.trim());
    return base.replace(path: '${base.path.replaceFirst(RegExp(r'/$'), '')}$path', query: null);
  }

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    if (_token.text.trim().isNotEmpty) 'Authorization': 'Bearer ${_token.text.trim()}',
  };

  void _log(String text) {
    if (!mounted) return;
    setState(() {
      _events.insert(0, '${DateTime.now().toLocal().toIso8601String().substring(11, 19)}  $text');
      if (_events.length > 100) _events.removeLast();
    });
  }

  Future<void> _connect() async {
    setState(() => _busy = true);
    try {
      final response = await http.get(_uri('/health'), headers: _headers).timeout(const Duration(seconds: 8));
      if (response.statusCode != 200) throw Exception('Health check HTTP ${response.statusCode}: ${response.body}');
      final wsBase = _server.text.trim().replaceFirst(RegExp(r'^http'), 'ws');
      final wsUri = Uri.parse('$wsBase/ws/notifications');
      await _eventSubscription?.cancel();
      await _channel?.sink.close();
      _channel = WebSocketChannel.connect(wsUri);
      await _channel!.ready;
      _channel!.sink.add('auth:${_token.text.trim()}');
      _eventSubscription = _channel!.stream.listen((event) {
        try {
          final data = jsonDecode(event.toString()) as Map<String, dynamic>;
          if (data['type'] == 'timer_expired') {
            _log('Timer finished: ${data['label']}');
          } else if (data['type'] != 'heartbeat' && data['type'] != 'connected') {
            _log('Notification: ${jsonEncode(data)}');
          }
          _channel?.sink.add('ping');
        } catch (_) {
          _log('Notification: $event');
        }
      }, onError: (Object error) => _log('Notification stream error: $error'));
      setState(() => _status = 'Connected to VisionGuideAI');
      _log('Connected: ${_server.text.trim()}');
    } catch (error) {
      setState(() => _status = 'Connection failed');
      _log('Connection failed: $error');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _listen() async {
    final available = await _speech.initialize(
      onStatus: (status) => setState(() => _listening = status == 'listening'),
      onError: (error) => _log('Speech recognition error: ${error.errorMsg}'),
    );
    if (!available) {
      _log('Speech recognition is unavailable on this device. Use the command text field.');
      return;
    }
    await _speech.listen(onResult: (result) {
      setState(() => _command.text = result.recognizedWords);
    }, listenFor: const Duration(seconds: 12), pauseFor: const Duration(seconds: 2));
    setState(() => _listening = true);
  }

  Future<void> _toggleWhisperRecording() async {
    try {
      if (!_whisperRecording) {
        if (!await _recorder.hasPermission()) {
          _log('Microphone permission was not granted.');
          return;
        }
        final directory = await getTemporaryDirectory();
        final filePath = '${directory.path}/visionguide_${DateTime.now().millisecondsSinceEpoch}.wav';
        await _recorder.start(const RecordConfig(encoder: AudioEncoder.wav, sampleRate: 16000, numChannels: 1), path: filePath);
        setState(() => _whisperRecording = true);
        _log('Recording audio locally. Tap Stop Whisper recording when finished.');
        return;
      }
      final filePath = await _recorder.stop();
      setState(() => _whisperRecording = false);
      if (filePath == null || !await File(filePath).exists()) {
        _log('No audio file was produced.');
        return;
      }
      setState(() => _busy = true);
      try {
        final uri = _uri('/api/v1/transcribe').replace(queryParameters: {'model': 'base'});
        final request = http.MultipartRequest('POST', uri);
        if (_token.text.trim().isNotEmpty) request.headers['Authorization'] = 'Bearer ${_token.text.trim()}';
        request.files.add(await http.MultipartFile.fromPath('audio', filePath, filename: 'voice.wav'));
        final streamed = await request.send().timeout(const Duration(seconds: 120));
        final response = await http.Response.fromStream(streamed);
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        if (response.statusCode < 200 || response.statusCode >= 300) throw Exception('Whisper HTTP ${response.statusCode}: ${response.body}');
        final transcript = (data['transcript'] ?? '').toString();
        setState(() => _command.text = transcript);
        _log('Local Whisper transcription complete: $transcript');
      } finally {
        try { await File(filePath).delete(); } catch (_) {}
        if (mounted) setState(() => _busy = false);
      }
    } catch (error) {
      if (mounted) setState(() { _whisperRecording = false; _busy = false; });
      _log('Whisper recording/transcription failed: $error');
    }
  }

  Future<void> _sendCommand({String? confirmationId}) async {
    final text = _command.text.trim();
    if (text.isEmpty && confirmationId == null) return;
    setState(() => _busy = true);
    try {
      final Uri uri;
      final Map<String, dynamic> payload;
      if (confirmationId != null) {
        uri = _uri('/api/v1/confirm');
        payload = {'confirmation_id': confirmationId, 'device_id': _deviceId, 'confirmed': confirmed};
      } else {
        uri = _uri('/api/v1/command');
        payload = {'text': text, 'device_id': _deviceId};
      }
      final response = await http.post(uri, headers: _headers, body: jsonEncode(payload)).timeout(const Duration(seconds: 60));
      final Map<String, dynamic> data = jsonDecode(response.body) as Map<String, dynamic>;
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw Exception('HTTP ${response.statusCode}: ${response.body}');
      }
      final result = (data['result'] is Map<String, dynamic>) ? data['result'] as Map<String, dynamic> : data;
      if (result['status'] == 'confirmation_required' && result['confirmation_id'] is String) {
        final preview = result['preview'] ?? {};
        final approve = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Confirm action'),
            content: SingleChildScrollView(child: Text('${result['message'] ?? 'Review this action.'}\n\n${const JsonEncoder.withIndent('  ').convert(preview)}')),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
              FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Confirm')),
            ],
          ),
        ) ?? false;
        final confirmation = await _sendConfirmation(result['confirmation_id'] as String, approve);
        _log(confirmation);
      } else {
        _log(const JsonEncoder.withIndent('  ').convert(data));
      }
    } catch (error) {
      _log('Command failed: $error');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<String> _sendConfirmation(String id, bool confirmed) async {
    final response = await http.post(_uri('/api/v1/confirm'), headers: _headers,
      body: jsonEncode({'confirmation_id': id, 'device_id': _deviceId, 'confirmed': confirmed})).timeout(const Duration(seconds: 60));
    if (response.statusCode < 200 || response.statusCode >= 300) throw Exception('Confirmation HTTP ${response.statusCode}: ${response.body}');
    return const JsonEncoder.withIndent('  ').convert(jsonDecode(response.body));
  }

  @override
  void dispose() {
    _eventSubscription?.cancel();
    _channel?.sink.close();
    _server.dispose(); _token.dispose(); _command.dispose();
    _speech.stop();
    _recorder.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('VisionGuideAI'),
        Text('Voice and cross-device command client', style: TextStyle(fontSize: 12, fontWeight: FontWeight.normal)),
      ])),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        TextField(controller: _server, decoration: const InputDecoration(labelText: 'VisionGuideAI server URL', hintText: 'http://192.168.1.10:8000')),
        const SizedBox(height: 8),
        TextField(controller: _token, obscureText: true, decoration: const InputDecoration(labelText: 'API bearer token', helperText: 'Required when the API binds beyond loopback. Never share this token.')),
        const SizedBox(height: 8),
        Row(children: [Expanded(child: Text(_status)), FilledButton(onPressed: _busy ? null : _connect, child: const Text('Connect'))]),
        const SizedBox(height: 20),
        TextField(controller: _command, minLines: 2, maxLines: 5, decoration: const InputDecoration(labelText: 'Command', hintText: 'Open YouTube, set a timer for five minutes, read my unread emails')),
        const SizedBox(height: 8),
        Wrap(spacing: 8, runSpacing: 8, children: [
          FilledButton.icon(onPressed: _busy ? null : () => _sendCommand(), icon: const Icon(Icons.send), label: const Text('Run command')),
          OutlinedButton.icon(onPressed: _busy ? null : (_listening ? () async { await _speech.stop(); setState(() => _listening = false); } : _listen),
            icon: Icon(_listening ? Icons.mic_off : Icons.mic), label: Text(_listening ? 'Stop listening' : 'Speak command')),
          OutlinedButton.icon(onPressed: _busy ? null : _toggleWhisperRecording,
            icon: Icon(_whisperRecording ? Icons.stop_circle : Icons.graphic_eq), label: Text(_whisperRecording ? 'Stop Whisper recording' : 'Record for Whisper')),
        ]),
        const SizedBox(height: 8),
        const Text('Sensitive operations display a confirmation preview before execution. “Record for Whisper” sends the temporary audio file to your configured VisionGuideAI server for local Whisper transcription; it is not sent to Gemini and the temporary upload is deleted after transcription. Camera narration remains controlled by the device client.'),
        const SizedBox(height: 20),
        Text('Activity', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        if (_events.isEmpty) const Text('No activity yet.'),
        ..._events.map((item) => Card(child: Padding(padding: const EdgeInsets.all(10), child: SelectableText(item)))),
      ]),
    );
  }
}
