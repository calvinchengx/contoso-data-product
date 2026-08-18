-- THE QUARANTINE SPLIT, ASSERTED FROM THE OTHER SIDE.
--
-- `silver_orders` keeps `not (quantity <= 0 or unit_price is null)` and
-- `silver_quarantine_orders` keeps the negation. Both read the same predicate
-- from the same CTE precisely so they cannot drift and lose or double a row --
-- but "cannot drift" is a claim about the code, and this is the check on it.
-- If a non-positive quantity ever reaches silver_orders, the split leaked.
--
-- A SINGULAR TEST RATHER THAN `dbt_utils.accepted_range`, which is what this
-- was. That was silver's only dependency on an external dbt package, and it
-- cost more than it bought: this project now ships inside `contoso-data-product`
-- and is resolved by `silver_dir()`, so a `packages.yml` would mean every cell
-- of the family runs `dbt deps` -- a network fetch into an installed package's
-- own directory -- before it can build silver. Gold has never needed one. Six
-- lines of SQL is the cheaper half of that trade.
select order_id, quantity
from {{ ref('silver_orders') }}
where quantity <= 0 or quantity is null
