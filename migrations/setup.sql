-- This cannot run on SQLite.
-- It has not been tested since the standard use case is SQLite.

BEGIN TRANSACTION;

CREATE VIEW player_match_join
-- WITH SCHEMABINDING -- SQL Server only?
AS
    SELECT match.tournament, match.round, player.team, player.surrogate
    FROM fllfms_match match
    INNER JOIN fllfms_player player
    ON match.id = player.match
    -- Play as many surrogate matches as you like, but really should only be 1.
    WHERE player.surrogate = 0
;

CREATE UNIQUE INDEX player_round_tournament_uniq ON player_match_join(tournament, round, team, surrogate);

COMMIT;
