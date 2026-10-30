// Who is who on the ward. Roles are told apart by an icon and a short mark, not by hue: colour
// in this app means the state of the work (whose turn, waiting, done, with the pharmacist,
// danger in the data), so it reads the same on every screen.

import type { RoleKey } from '../auth';
import { Icon, type IconName } from './viz';

export const ROLE: Record<RoleKey, { title: string; mark: string; icon: IconName; does: string }> = {
  nurse: { title: 'Ward nurse', mark: 'N', icon: 'person', does: 'Admits the patient, pulls ABHA records with consent, types the list as written' },
  lab: { title: 'Lab technician', mark: 'Lab', icon: 'flask', does: 'Enters eGFR; the kidney-dose checks re-run on it' },
  pharmacist: { title: 'Pharmacist', mark: 'Ph', icon: 'pill', does: 'Confirms names the system would not guess, answers alerts handed over' },
  prescriber: { title: 'Prescriber', mark: 'Rx', icon: 'stethoscope', does: 'Accepts, overrides with a reason, or defers each alert' },
  reviewer: { title: 'Reviewer', mark: 'Rv', icon: 'eye', does: 'Reads everything; makes no entries and no decisions' },
};

/** The order a ward record moves through. */
export const CARE_PATH: RoleKey[] = ['nurse', 'lab', 'pharmacist', 'prescriber'];

export function RoleTile({ role, size = 32 }: { role: RoleKey; size?: number }) {
  return (
    <span className="role-tile" style={{ width: size, height: size }} title={ROLE[role].title} aria-hidden="true">
      <Icon name={ROLE[role].icon} size={Math.round(size * 0.5)} />
    </span>
  );
}

export function RoleName({ role }: { role: RoleKey }) {
  return <span className="role-name"><RoleTile role={role} size={20} />{ROLE[role].title}</span>;
}
