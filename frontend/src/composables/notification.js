import { createApp } from 'vue';
import NotificationComponent from '@/components/UI/Notification.vue';

const notifications = [];

export const notify = {
	success(message, duration = 3000) {
		this.show(message, 'success', duration);
	},
	error(message, duration = 5000) {
		this.show(message, 'error', duration);
	},
	warning(message, duration = 4000) {
		this.show(message, 'warning', duration);
	},
	info(message, duration = 3000) {
		this.show(message, 'info', duration);
	},

  show(message, type = 'info', duration = 3000) {
	const container = document.createElement('div');
	document.body.appendChild(container);

		const app = createApp(NotificationComponent, {
			message,
			type,
			duration,
			onClose: () => {
				app.unmount();
				document.body.removeChild(container);
				const index = notifications.indexOf(app);
				if (index > -1) notifications.splice(index, 1);
			}
		});

		notifications.push(app);
		app.mount(container);
	}
};