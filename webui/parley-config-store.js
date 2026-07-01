import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";
import { toastFrontendError } from "/components/notifications/notification-store.js";

const _PLATFORMS = {
  revolt:  { channelsUrl: 'channels',        updateUrl: 'update_channels',        title: 'Revolt Watched Channels',  cfgObj: (c) => c,         },
  discord: { channelsUrl: 'discord_channels', updateUrl: 'discord_update_channels', title: 'Discord Watched Channels', cfgObj: (c) => c.discord, },
  slack:   { channelsUrl: 'slack_channels',   updateUrl: 'slack_update_channels',   title: 'Slack Watched Channels',   cfgObj: (c) => c.slack,   },
};

export const store = createStore("parleyConfig", {
  // Channel-picker modal state
  open: false,
  title: '',
  allChannels: true,
  channels: [],
  saving: false,
  refreshing: false,
  _onSave: null,
  _onRefresh: null,

  init(config, context = null) {},
  bindConfig(config) {},
  cleanup() {},

  chSummary(val) {
    const ids = Array.isArray(val)
      ? val.filter(Boolean)
      : (val || '').split(',').map((s) => s.trim()).filter(Boolean);
    if (!ids.length) return 'All channels';
    return ids.length + ' channel' + (ids.length === 1 ? '' : 's') + ' selected';
  },

  async openWatchedPicker(platform, config, btn) {
    const p        = _PLATFORMS[platform];
    const origText = btn.textContent;

    btn.disabled    = true;
    btn.textContent = 'Loading…';

    try {
      const data = await callJsonApi(`/plugins/parley/${p.channelsUrl}`);

      if (data.not_configured) {
        const hint = {
          revolt:  'Save your bot token and server ID first.',
          discord: 'Save your bot token and guild ID first.',
          slack:   'Save your bot token first.',
        }[platform];
        throw new Error(`${platform.charAt(0).toUpperCase() + platform.slice(1)} is not configured — ${hint}`);
      }
      if (!data.ok) {
        throw new Error(data.error || `Cannot connect to ${platform} server.`);
      }

      const textChannels = (data.channels || []).filter((c) => c.type === 'TextChannel');
      if (!textChannels.length) {
        throw new Error('No text channels found. Check the bot has access to at least one channel.');
      }

      const cfgObj     = p.cfgObj(config);
      const currentVal = cfgObj.watched_channels;
      const watchedIds = Array.isArray(currentVal)
        ? currentVal.filter(Boolean)
        : (currentVal || '').split(',').map((s) => s.trim()).filter(Boolean);

      this.show({
        title:    p.title,
        channels: textChannels,
        watchedIds,

        onSave: async (ids) => {
          const res = await callJsonApi(`/plugins/parley/${p.updateUrl}`, { watched_channels: ids });
          if (!res.ok) throw new Error(res.error || 'Save failed');
          // Update reactive config so the x-text summary re-renders
          cfgObj.watched_channels = ids;
        },

        onRefresh: async () => {
          const r = await callJsonApi(`/plugins/parley/${p.channelsUrl}`);
          if (!r.ok) throw new Error(r.error || 'Refresh failed');
          return (r.channels || []).filter((c) => c.type === 'TextChannel');
        },
      });

    } catch (e) {
      toastFrontendError(e.message || String(e), 'Parley');
    } finally {
      btn.disabled    = false;
      btn.textContent = origText;
    }
  },

  show(opts) {
    this.title      = opts.title || 'Watched Channels';
    this._onSave    = opts.onSave;
    this._onRefresh = opts.onRefresh;
    const watched = opts.watchedIds || [];
    this.allChannels = watched.length === 0;
    this._apply(opts.channels || [], new Set(watched));
    this.open = true;
  },

  close() {
    this.open = false;
  },

  toggle(id) {
    const ch = this.channels.find((c) => c.id === id);
    if (ch) ch.selected = !ch.selected;
  },

  async save() {
    if (!this._onSave || this.saving) return;
    const ids = this.allChannels
      ? []
      : this.channels.filter((c) => c.selected).map((c) => c.id);
    this.saving = true;
    try {
      await this._onSave(ids);
      this.open = false;
    } catch (e) {
      // leave open; caller shows its own error
    } finally {
      this.saving = false;
    }
  },

  async refresh() {
    if (!this._onRefresh || this.refreshing) return;
    this.refreshing = true;
    try {
      const updated = await this._onRefresh();
      if (Array.isArray(updated)) {
        const draft = new Set(this.channels.filter((c) => c.selected).map((c) => c.id));
        this._apply(updated, draft.size ? draft : null);
      }
    } finally {
      this.refreshing = false;
    }
  },

  _apply(list, selectedIds) {
    this.channels = list.map((ch) => ({
      ...ch,
      selected: selectedIds === null || selectedIds.has(ch.id),
    }));
  },
});
