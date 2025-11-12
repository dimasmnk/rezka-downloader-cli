def choose_preferred_quality(videos_keys):
    # hardcoded exact labels (user-specified). We check in reverse to prefer higher qualities.
    preferred = ['1080p Ultra', '1080p', '720p', '480p', '360p']
    for q in preferred:
        if q in videos_keys:
            return q
    return None