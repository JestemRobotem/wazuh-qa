import { validateElementTextIncludes } from '../../../utils/driver';
import { connectionSuccessToast } from '../../../pageobjects/settings/api-configuration.page';

Then('The connection success toast is displayed', () => {
  validateElementTextIncludes(connectionSuccessToast, 'Settings. Connection success');
});