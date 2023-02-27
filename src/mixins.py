"""Example Mixin providing one method of extending the heartbeat server's behaviour."""
import twilio
import os


class TwilioMixin:
    def notify(self, pid):
        if "auth_token" not in self.__dict__:
            self.get_env()

        process_name = self.clients[pid]["process_name"]
        msg = f"Missed Heartbeat | PID: {pid} | Identifier: {process_name}"

        client = twilio.rest.Client(self.sid, self.auth_token)

        try:
            message = client.messages.create(
                from_=self.from_,
                to=self.to,
                body=msg
            )

            print(f"Message Sent: {message.sid}")

        except twilio.TwilioRestException as e:
            print(e)

    def get_env(self):
        self.sid = os.environ["twilio_sid"]
        self.auth_token = os.environ["twilio_auth"]
        self.from_ = os.environ["twilio_from"]
        self.to = os.environ["twilio_to"]