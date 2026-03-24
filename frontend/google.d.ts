interface GoogleCredentialResponse {
  credential?: string;
}

interface GoogleAccountsId {
  initialize(options: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void | Promise<void>;
  }): void;
  cancel(): void;
  renderButton(
    parent: HTMLElement,
    options: {
      theme?: "outline" | "filled_blue" | "filled_black";
      size?: "large" | "medium" | "small";
      shape?: "rectangular" | "pill" | "circle" | "square";
      text?: "signin_with" | "signup_with" | "continue_with" | "signin";
      width?: number;
    }
  ): void;
}

interface GoogleNamespace {
  accounts: {
    id: GoogleAccountsId;
  };
}

interface Window {
  google?: GoogleNamespace;
}
