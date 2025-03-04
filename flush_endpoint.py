@app.route('/api/flush-tts-entries', methods=['POST'])
def flush_tts_entries():
    """Remove TTS entries where the audio file doesn't exist anymore"""
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        
        # Get all TTS entries
        c.execute("SELECT message_id, file_path FROM tts_logs")
        entries = c.fetchall()
        
        # Track statistics
        total = len(entries)
        removed = 0
        
        # Check each entry
        for entry_id, file_path in entries:
            if not file_path:
                # If file path is None or empty, remove the entry
                c.execute("DELETE FROM tts_logs WHERE message_id = ?", (entry_id,))
                removed += 1
                continue
                
            # Normalize the path
            if file_path.startswith('static/'):
                full_path = os.path.join(os.getcwd(), file_path)
            else:
                full_path = os.path.join(os.getcwd(), 'static', file_path)
            
            # Check if file exists
            if not os.path.exists(full_path):
                # If file doesn't exist, remove the entry
                c.execute("DELETE FROM tts_logs WHERE message_id = ?", (entry_id,))
                removed += 1
        
        # Commit changes and close connection
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Cleaned up TTS entries ({removed} of {total} entries removed)',
            'removed': removed,
            'total': total
        })
    except Exception as e:
        app.logger.error(f"Error flushing TTS entries: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500