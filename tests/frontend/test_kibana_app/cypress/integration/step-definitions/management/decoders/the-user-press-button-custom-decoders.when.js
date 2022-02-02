import { When } from 'cypress-cucumber-preprocessor/steps';
import { clickElement, getElement } from '../../../utils/driver';
import { customDecodersButtonSelector } from '../../../pageobjects/wazuh-menu/decoders.page';

When('The user press button custom decoders', () => {
  cy.wait(2000)
  clickElement(customDecodersButtonSelector);
});
