class EmailProvider:
    @staticmethod
    def sendmail(addr, text, subject, html=None):
        raise NotImplementedError
