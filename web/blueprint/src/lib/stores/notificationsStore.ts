import type {ToastNotificationProps} from 'carbon-components-svelte/types/Notification/ToastNotification.svelte';
import {getContext, hasContext, setContext} from 'svelte';
import {writable} from 'svelte/store';

const NOTIFICATIONS_CONTEXT = 'NOTIFICATIONS_CONTEXT';

export interface Notification {
  kind: ToastNotificationProps['kind'];
  title: string;
  subtitle?: string;
  message: string;
}

export interface NotificationsState {
  notifications: Notification[];
}

export type NotificationsStore = ReturnType<typeof createNotificationsStore>;

export function createNotificationsStore() {
  const {subscribe, set, update} = writable<NotificationsState>({notifications: []});

  return {
    subscribe,
    set,
    update,
    reset() {
      set({notifications: []});
    },
    addNotification(notification: Notification) {
      update(state => {
        state.notifications.push(notification);
        return state;
      });
    },
    removeNotification(notification: Notification) {
      update(state => {
        state.notifications = state.notifications.filter(n => n !== notification);
        return state;
      });
    }
  };
}

export function setNotificationsContext(store: NotificationsStore) {
  setContext(NOTIFICATIONS_CONTEXT, store);
}

export function getNotificationsContext(): NotificationsStore {
  if (!hasContext(NOTIFICATIONS_CONTEXT)) throw new Error('NotificationContext not found');
  return getContext<NotificationsStore>(NOTIFICATIONS_CONTEXT);
}
