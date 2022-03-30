import { When } from 'cypress-cucumber-preprocessor/steps';
import { forceClickElement, elementIsVisible} from '../../utils/driver';
import { BASIC_MODULES } from '../../utils/mappers/basic-modules-mapper';
When('The user goes to {}', (moduleName) => {
  cy.wait(5000);
  elementIsVisible(BASIC_MODULES[moduleName]);
  forceClickElement(BASIC_MODULES[moduleName]);
});
