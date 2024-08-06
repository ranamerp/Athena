#region schedule
CURRENTWEEK = """
	WITH currweek AS (
		SELECT 
			matches.*, 
			DATE_PART('doy', to_timestamp((matches.starttime - 21600000) / 1000)) AS day,
			DENSE_RANK() OVER(ORDER BY DATE_PART('doy', to_timestamp((matches.starttime - 21600000) / 1000))) AS rank
		FROM 
			stats.matches
		WHERE 
        	to_timestamp(starttime / 1000) > date_trunc('week', NOW()) + INTERVAL '1 DAY'
			AND to_timestamp(starttime / 1000) < date_trunc('week', NOW()) + INTERVAL '8 DAYS'
		)
	SELECT * FROM currweek ORDER BY day, starttime asc;
"""

NEXTWEEK = """
	WITH nextweek AS (
	SELECT 
		matches.*, 
		DATE_PART('doy', to_timestamp((matches.starttime - 21600000) / 1000)) AS day,
		DENSE_RANK() OVER(ORDER BY DATE_PART('doy', to_timestamp((matches.starttime - 21600000) / 1000))) AS rank
	FROM 
		stats.matches
	WHERE 
		to_timestamp(starttime/1000) > date_trunc('week', to_timestamp(
            (select starttime FROM stats.matches 
            WHERE to_timestamp(starttime / 1000) > NOW() ORDER BY starttime ASC LIMIT 1)/1000)::timestamp) + INTERVAL '1 DAY'
	AND 
    	to_timestamp(starttime/1000) < date_trunc('week', to_timestamp(										
			(select starttime FROM stats.matches 
			WHERE to_timestamp(starttime / 1000) > NOW() ORDER BY starttime ASC LIMIT 1)/1000)::timestamp) + INTERVAL '8 days'
	) SELECT * FROM nextweek ORDER BY day, starttime asc;


"""

#endregion

#region preds
LBALLSEASON = """
WITH allpreds AS (
    SELECT 
        predictions.user_id, 
        COUNT(predictions.id) AS total, 
        SUM(CASE WHEN mWinner = winner THEN 1 ELSE 0 END) AS winner_correct, 
        SUM(CASE WHEN mWinner = winner AND mScore = loser_score THEN 1 ELSE 0 END) AS maps_correct 
    FROM 
        (SELECT 
            *, 
            (CASE WHEN GREATEST(htscore, atscore) = htscore THEN htshort WHEN GREATEST(htscore, atscore) = atscore THEN atshort ELSE NULL END) mWinner, 
            LEAST(htscore, atscore) mScore 
        FROM 
            athena.matches
        ) m 
        INNER JOIN athena.predictions ON m.id = predictions.match_id WHERE status = 'CONCLUDED' GROUP BY user_id
) 
SELECT 
    user_id, 
    total, 
    winner_correct, 
    ((winner_correct::NUMERIC / total::NUMERIC) * 100)::INTEGER AS winner_percent, 
    maps_correct, ((maps_correct::NUMERIC / total::NUMERIC) * 100)::INTEGER AS maps_percent 
FROM 
    allpreds 
WHERE 
    total >= $1 
ORDER BY
"""

LBCURRENTEVENT = """
WITH allpreds AS (
    SELECT 
        predictions.user_id, 
        COUNT(predictions.id) AS total, 
        SUM(CASE WHEN mWinner = winner THEN 1 ELSE 0 END) AS winner_correct, 
        SUM(CASE WHEN mWinner = winner AND mScore = loser_score THEN 1 ELSE 0 END) AS maps_correct 
    FROM 
        (SELECT 
            matches.*,
			w.event, 
            (CASE WHEN GREATEST(htscore, atscore) = htscore THEN htshort WHEN GREATEST(htscore, atscore) = atscore THEN atshort ELSE NULL END) mWinner, 
            LEAST(htscore, atscore) mScore 
        FROM 
            athena.matches INNER JOIN (SELECT weeks.week_number, weeks.event FROM athena.weeks WHERE weeks.event = $2) w ON matches.week_number = w.week_number
        ) m 
        INNER JOIN athena.predictions ON m.id = predictions.match_id WHERE status = 'CONCLUDED' GROUP BY user_id
) 
SELECT 
    user_id, 
    total, 
    winner_correct, 
    ((winner_correct::NUMERIC / total::NUMERIC) * 100)::INTEGER AS winner_percent, 
    maps_correct, ((maps_correct::NUMERIC / total::NUMERIC) * 100)::INTEGER AS maps_percent 
FROM 
    allpreds 
WHERE 
    total >= $1
ORDER BY
"""

LBWEEK = """
WITH allpreds AS (
    SELECT 
        predictions.user_id, 
        COUNT(predictions.id) AS total, 
        SUM(CASE WHEN mWinner = winner THEN 1 ELSE 0 END) AS winner_correct, 
        SUM(CASE WHEN mWinner = winner AND mScore = loser_score THEN 1 ELSE 0 END) AS maps_correct 
    FROM 
        (SELECT 
            matches.*,
            (CASE WHEN GREATEST(htscore, atscore) = htscore THEN htshort WHEN GREATEST(htscore, atscore) = atscore THEN atshort ELSE NULL END) mWinner, 
            LEAST(htscore, atscore) mScore 
        FROM 
            athena.matches INNER JOIN (SELECT weeks.week_number FROM athena.weeks WHERE weeks.week_number = $2) w ON matches.week_number = w.week_number
        ) m 
        INNER JOIN athena.predictions ON m.id = predictions.match_id WHERE status = 'CONCLUDED' GROUP BY user_id
) 
SELECT 
    user_id, 
    total, 
    winner_correct, 
    ((winner_correct::NUMERIC / total::NUMERIC) * 100)::INTEGER AS winner_percent, 
    maps_correct, ((maps_correct::NUMERIC / total::NUMERIC) * 100)::INTEGER AS maps_percent 
FROM 
    allpreds 
WHERE 
    total >= $1
ORDER BY
"""

ALLMATCHES = """
WITH upcoming as (
SELECT 
	matches.*,
	ht.pickem_id as htid,
	att.pickem_id as atid
from stats.matches
INNER JOIN stats.teams ht
ON matches.htshort = ht.code
INNER JOIN stats.teams att
ON matches.atshort = att.code

)
SELECT *
FROM upcoming
where pickem_id is not null
order by starttime asc
"""

UPCOMINGMATCHESINWEEK = """
WITH upcoming as (
SELECT 
	matches.*,
	ht.pickem_id as htid,
	att.pickem_id as atid,
	DATE_PART('doy', to_timestamp((matches.starttime - 21600000) / 1000)) AS day,
	DENSE_RANK() OVER(ORDER BY DATE_PART('doy', to_timestamp((matches.starttime - 21600000) / 1000))) AS rank
from stats.matches
INNER JOIN stats.teams ht
ON matches.htshort = ht.code
INNER JOIN stats.teams att
ON matches.atshort = att.code
WHERE to_timestamp(starttime / 1000) > date_trunc('week', NOW()) + INTERVAL '1 DAY'
			AND to_timestamp(starttime / 1000) < date_trunc('week', NOW()) + INTERVAL '8 DAYS'
ORDER BY day, starttime
)
SELECT *
FROM upcoming
WHERE starttime > $1



"""

USERPREDS = """
WITH allpreds AS (
    SELECT 
        m.*, 
        predictions.user_id, 
        predictions.winner as pwinner, 
        predictions.loser, 
        predictions.match_id, 
        predictions.winner_score AS winner_score_int,
        predictions.loser_score AS loser_score_int,
        (CASE WHEN predictions.winner_score IS NULL THEN ' ' ELSE CONCAT(predictions.winner_score::char, ' - ') END) winner_score, 
        (CASE WHEN predictions.loser_score IS NULL THEN ' ' ELSE predictions.loser_score::char END) loser_score, 
        DATE_PART('doy', to_timestamp((m.starttime - 21600000) / 1000)) AS day, DENSE_RANK() OVER(ORDER BY DATE_PART('doy', to_timestamp((m.starttime - 21600000) / 1000))) AS rank 
    FROM 
        (SELECT *, (CASE WHEN GREATEST(htscore, atscore) = htscore THEN htshort WHEN GREATEST(htscore, atscore) = atscore THEN atshort ELSE NULL END) mWinner, LEAST(htscore, atscore) mScore FROM stats.matches) m INNER JOIN athena.predictions ON m.id = predictions.match_id
    WHERE
		predictions.user_id = $1
) 
SELECT 
    *,
    (CASE WHEN state = 'pending' THEN ' ' WHEN mWinner = pwinner AND mScore = loser_score_int THEN '✅' WHEN mWinner = pwinner THEN '🟩' WHEN mWinner != pwinner THEN '🟥' ELSE ' ' END) indicator 
FROM 
    allpreds 
ORDER BY 
    rank, 
    starttime
"""

ALLPREDSFORMATCH = """
WITH allpreds AS (
    SELECT 
        matches.*, 
        predictions.user_id, 
        predictions.winner, 
        predictions.loser, 
        predictions.match_id, 
        (CASE WHEN predictions.winner_score IS NULL THEN ' ' ELSE CONCAT(predictions.winner_score::char, '-') END) winner_score, 
        (CASE WHEN predictions.loser_score IS NULL THEN '  ' ELSE predictions.loser_score::char END) loser_score, 
        (CASE WHEN predictions.winner_score IS NULL THEN CONCAT(predictions.winner, ' W-L: ') ELSE CONCAT(predictions.winner, ' ', predictions.winner_score::char, '-', predictions.loser_score::char, ': ') END) scoreline
    FROM 
        stats.matches INNER JOIN athena.predictions ON matches.id = predictions.match_id
    WHERE 
		matches.id = (SELECT id FROM stats.matches WHERE (htshort = $1 AND atshort = $2) OR (atshort = $1 AND htshort = $2) ORDER BY (GREATEST(NOW(), to_timestamp(starttime / 1000)) - LEAST(NOW(), to_timestamp(starttime / 1000))) LIMIT 1)
) 
SELECT 
    * 
FROM 
    allpreds;
"""

USERPREDSTATS = """
WITH allpreds AS (
    SELECT 
        predictions.user_id, 
        COUNT(predictions.id) AS total, 
        SUM(CASE WHEN mWinner = predictions.winner THEN 1 ELSE 0 END) AS winner_correct, 
        SUM(CASE WHEN mWinner = predictions.winner AND mScore = loser_score THEN 1 ELSE 0 END) AS maps_correct 
    FROM 
        (SELECT 
            *, 
            (CASE WHEN GREATEST(htscore, atscore) = htscore THEN htshort WHEN GREATEST(htscore, atscore) = atscore THEN atshort ELSE NULL END) mWinner, 
            LEAST(htscore, atscore) mScore 
        FROM stats.matches) m 
        INNER JOIN athena.predictions ON m.id = predictions.match_id 
    WHERE 
        state = 'concluded' 
    GROUP BY user_id
),
statlines AS(
    SELECT 
        user_id, 
        total, 
        winner_correct, 
        ((winner_correct::NUMERIC / total::NUMERIC) * 100)::INTEGER AS winner_percent, 
        maps_correct, ((maps_correct::NUMERIC / total::NUMERIC) * 100)::INTEGER AS maps_percent,
        RANK() OVER(ORDER BY winner_correct DESC, maps_correct DESC) AS winner_rank,
        RANK() OVER(ORDER BY maps_correct DESC, total DESC) AS maps_rank
    FROM 
        allpreds
	WHERE total >= $2
)
SELECT
    *
FROM
    statlines
WHERE user_id = $1
"""

PAIDOUT = """
WITH allpreds AS (
    SELECT 
        m.*, 
		predictions.id AS pred_id,
        predictions.user_id, 
		predictions.paidout,
        predictions.winner as pwinner, 
        predictions.loser, 
        predictions.match_id, 
        predictions.winner_score AS winner_score_int,
        predictions.loser_score AS loser_score_int,
        (CASE WHEN predictions.winner_score IS NULL THEN ' ' ELSE CONCAT(predictions.winner_score::char, ' - ') END) winner_score, 
        (CASE WHEN predictions.loser_score IS NULL THEN ' ' ELSE predictions.loser_score::char END) loser_score
    FROM 
        (SELECT id, state, (CASE WHEN GREATEST(htscore, atscore) = htscore THEN htshort WHEN GREATEST(htscore, atscore) = atscore THEN atshort ELSE NULL END) mWinner, LEAST(htscore, atscore) mScore FROM stats.matches) m INNER JOIN athena.predictions ON m.id = predictions.match_id
) 
SELECT 
	id,
	pred_id,
    user_id,
	state,
	paidout,
    (CASE WHEN state = 'pending' THEN ' ' WHEN mWinner = pwinner AND mScore = loser_score_int THEN 'm' WHEN mWinner = pwinner THEN 'w' WHEN mWinner != pwinner THEN 'l' ELSE ' ' END) indicator 
FROM 
    allpreds
WHERE
	id = $1
	AND
	paidout = FALSE;
"""
#endregion

#region cards
SETRARITYSELECTION = """
SELECT
	*
FROM
	tcg.cards INNER JOIN tcg.set_contents ON cards.id = set_contents.card_id
WHERE
	set_contents.set_name = $1
	AND
	cards.rarity = $2;
"""

CARDSINPACK = """
SELECT
	circulation.id AS circulation_id,
	cards.id AS id,
	cards.name AS name,
	cards.description AS description,
	cards.picture AS picture,
	cards.rarity AS rarity,
	sets.set_name,
	sets.cover AS cover,
	circulation.id AS count
FROM
	tcg.packs 
	INNER JOIN tcg.contents ON packs.id = contents.pack_id
	INNER JOIN tcg.sets ON packs.set_name = sets.set_name
	INNER JOIN tcg.circulation ON contents.circulation_id = circulation.id
	INNER JOIN tcg.cards ON circulation.card = cards.id
WHERE
	packs.id = $1;
"""

GETUSERCOLLECTION = """
SELECT
	cards.id,
	cards.name AS name,
	cards.rarity,
	cards.description,
	cards.picture AS picture,
	set_contents.set_name,
	sets.cover,
	COUNT(cards.id)
FROM
	tcg.circulation INNER JOIN tcg.cards ON circulation.card = cards.id
	INNER JOIN tcg.set_contents ON set_contents.card_id = circulation.card
	INNER JOIN tcg.sets ON sets.set_name = set_contents.set_name
WHERE
	circulation.owner = $1
GROUP BY
	cards.id,
	cards.picture,
	cards.rarity,
	cards.description,
	cards.picture,
	set_contents.set_name,
	sets.cover
ORDER BY 
	rarity DESC,
	COUNT(cards.id) DESC;	
"""
	
SEARCHUSERCOLLECTION = """
SELECT
	cards.id,
	cards.name AS name,
	cards.rarity,
	cards.description,
	cards.picture AS picture,
	set_contents.set_name,
	sets.cover,
	COUNT(cards.id)
FROM
	tcg.circulation INNER JOIN tcg.cards ON circulation.card = cards.id
	INNER JOIN tcg.set_contents ON set_contents.card_id = circulation.card
	INNER JOIN tcg.sets ON sets.set_name = set_contents.set_name
WHERE
	circulation.owner = $1
	AND
	((cards.rarity::text ILIKE $2) OR (cards.name ILIKE $3) OR (set_contents.set_name ILIKE $2) OR (cards.description ILIKE $3))
GROUP BY
	cards.id,
	cards.picture,
	cards.rarity,
	cards.description,
	cards.picture,
	set_contents.set_name,
	sets.cover
ORDER BY 
	rarity DESC,
	COUNT(cards.id) DESC;	
"""


GETPACKSINSTORE = """
SELECT 
	sets.cover,
	packs.card_count,
	packs.set_name, 
	COUNT(packs.set_name) 
FROM 
	tcg.packs INNER JOIN tcg.sets ON packs.set_name = sets.set_name
WHERE 
	owner = 0 
GROUP BY 
	packs.set_name,
	sets.cover,
	packs.card_count
ORDER BY
	packs.set_name;
	-- COUNT(packs.set_name) DESC;
"""

FETCHUSERCARD = """
SELECT
	circulation.id AS id,
	cards.name AS name,
	cards.description AS description,
	cards.picture AS picture,
	cards.rarity AS rarity,
	cards.id AS cardID,
	sets.cover,
	sets.set_name
FROM
	tcg.circulation 
	INNER JOIN tcg.cards ON circulation.card = cards.id
	INNER JOIN tcg.set_contents ON cards.id = set_contents.card_id
	INNER JOIN tcg.sets ON sets.set_name = set_contents.set_name
WHERE
	(cards.id::TEXT = $1 OR cards.name ILIKE $1)
	AND
	circulation.owner = $2;
"""

FETCHUSERCARDINCIRCULATION = """
SELECT
	circulation.id AS id,
	cards.name AS name,
	cards.description AS description,
	cards.picture AS picture,
	cards.rarity AS rarity,
	cards.id AS cardID,
	sets.cover,
	sets.set_name
FROM
	tcg.circulation 
	INNER JOIN tcg.cards ON circulation.card = cards.id
	INNER JOIN tcg.set_contents ON cards.id = set_contents.card_id
	INNER JOIN tcg.sets ON sets.set_name = set_contents.set_name
WHERE
	(circulation.id::TEXT = $1 OR cards.name ILIKE $1)
	AND
	circulation.owner = $2;
"""

ALLUSERTRADES = """
SELECT
	*,
	DATE_PART('day', NOW() - created_at) age
FROM
	tcg.trades
	INNER JOIN (
		SELECT
			offers.trade_id AS cID,
			SUM(CASE WHEN cards.rarity = 'Common' THEN 1
				WHEN cards.rarity = 'Uncommon' THEN 2
				WHEN cards.rarity = 'Rare' THEN 3
				WHEN cards.rarity = 'Epic' THEN 4
				WHEN cards.rarity = 'Legendary' THEN 5
				END) AS items
		FROM 
			tcg.trades
			INNER JOIN tcg.offers ON (trades.creator = offers.offerer AND trades.id = offers.trade_id)
			INNER JOIN tcg.circulation ON circulation.id = offers.item
			INNER JOIN tcg.cards ON circulation.card = cards.id
		WHERE
			trade_id IN (
				SELECT
					id
				FROM
					trades
				WHERE
					creator = $1
			)
		GROUP BY 
			offers.trade_id,
			offerer
	) c ON c.cID = trades.id
	LEFT JOIN (
		SELECT
			trade_id AS mID,
			item AS amount
		FROM 
			tcg.offers
		WHERE 
			type = 'Currency'
			AND 
			offerer = $1 
	) m ON m.mID = trades.id
WHERE
	trades.creator = $1
ORDER BY 
	created_at DESC,
	items DESC;
"""



ALLTRADES = """
SELECT
	*,
	DATE_PART('day', NOW() - created_at) age
FROM
	tcg.trades
	INNER JOIN (
		SELECT
			offers.trade_id AS cID,
			SUM(CASE WHEN cards.rarity = 'Common' THEN 1
				WHEN cards.rarity = 'Uncommon' THEN 2
				WHEN cards.rarity = 'Rare' THEN 3
				WHEN cards.rarity = 'Epic' THEN 4
				WHEN cards.rarity = 'Legendary' THEN 5
				END) AS items
		FROM 
			tcg.trades
			INNER JOIN tcg.offers ON (trades.creator = offers.offerer AND trades.id = offers.trade_id)
			INNER JOIN tcg.circulation ON circulation.id = offers.item
			INNER JOIN tcg.cards ON circulation.card = cards.id
		GROUP BY 
			offers.trade_id,
			offerer
	) c ON c.cID = trades.id
	LEFT JOIN (
		SELECT
			trade_id AS mID,
			item AS amount
		FROM 
			offers
		WHERE 
			type = 'Currency'
	) m ON m.mID = trades.id
ORDER BY 
	created_at DESC,
	items DESC;
"""

USEROFFERS = """
SELECT 
	circulation.id AS circ_id,
	cards.id AS card_id,
	cards.rarity AS rarity,
	cards.name AS name,
	DATE_PART('day', NOW() - offers.created_at) age
FROM 
	tcg.offers 
	LEFT JOIN tcg.circulation ON circulation.id = offers.item
	LEFT JOIN tcg.cards ON circulation.card = cards.id
WHERE 
	offers.type = 'Card'
	AND
	offers.trade_id = $1 
	AND 
	offers.offerer = $2;
"""

CREATOROFFERSONTRADE = """
WITH total_value AS (
	SELECT
		offers.offerer,
		SUM(CASE WHEN cards.rarity = 'Common' THEN 1
				WHEN cards.rarity = 'Uncommon' THEN 2
				WHEN cards.rarity = 'Rare' THEN 3
				WHEN cards.rarity = 'Epic' THEN 4
				WHEN cards.rarity = 'Legendary' THEN 5
				END) AS value
	FROM 
		tcg.offers 
		INNER JOIN tcg.circulation ON circulation.id = offers.item
		INNER JOIN tcg.cards ON circulation.card = cards.id
	WHERE 
		offers.trade_id = $1 
	GROUP BY 
		offerer
)
SELECT
	*
FROM
	total_value
	LEFT JOIN (SELECT offerer AS oID, item AS currency FROM tcg.offers WHERE type = 'Currency' AND trade_id = $1) c ON c.oID = total_value.offerer
WHERE 
	offerer = $2
"""

ALLOFFERSONTRADE = """
WITH total_value AS (
	SELECT
		offers.offerer,
		SUM(CASE WHEN cards.rarity = 'Common' THEN 1
				WHEN cards.rarity = 'Uncommon' THEN 2
				WHEN cards.rarity = 'Rare' THEN 3
				WHEN cards.rarity = 'Epic' THEN 4
				WHEN cards.rarity = 'Legendary' THEN 5
				END) AS value
	FROM 
		tcg.offers 
		INNER JOIN tcg.circulation ON circulation.id = offers.item
		INNER JOIN tcg.cards ON circulation.card = cards.id
	WHERE 
		offers.trade_id = $1 
	GROUP BY 
		offerer
)
SELECT
	*
FROM
	total_value
	LEFT JOIN (SELECT offerer AS oID, item AS currency FROM tcg.offers WHERE type = 'Currency' AND trade_id = $1) c ON c.oID = total_value.offerer
WHERE 
	offerer != $2
ORDER BY
	total_value.value DESC;
"""

COLLECTIONSTATS = """
SELECT
	'All Sets' AS set_name,
	SUM(CASE WHEN cards.rarity = 'Common' THEN 1 ELSE 0 END) commons,
	SUM(CASE WHEN cards.rarity = 'Uncommon' THEN 1 ELSE 0 END) uncommons,
	SUM(CASE WHEN cards.rarity = 'Rare' THEN 1 ELSE 0 END) rares,
	SUM(CASE WHEN cards.rarity = 'Epic' THEN 1 ELSE 0 END) epics,
	SUM(CASE WHEN cards.rarity = 'Legendary' THEN 1 ELSE 0 END) legendaries,
	COUNT(1) as total
FROM
	tcg.circulation
	INNER JOIN tcg.cards ON circulation.card = cards.id
	INNER JOIN tcg.set_contents ON set_contents.card_id = cards.id
WHERE
	circulation.owner = $1;
"""


COLLECTIONSTATSBYSET = """
SELECT
	set_contents.set_name,
	SUM(CASE WHEN cards.rarity = 'Common' THEN 1 ELSE 0 END) commons,
	SUM(CASE WHEN cards.rarity = 'Uncommon' THEN 1 ELSE 0 END) uncommons,
	SUM(CASE WHEN cards.rarity = 'Rare' THEN 1 ELSE 0 END) rares,
	SUM(CASE WHEN cards.rarity = 'Epic' THEN 1 ELSE 0 END) epics,
	SUM(CASE WHEN cards.rarity = 'Legendary' THEN 1 ELSE 0 END) legendaries,
	COUNT(set_contents.set_name) as total
FROM
	tcg.circulation
	INNER JOIN tcg.cards ON circulation.card = cards.id
	INNER JOIN tcg.set_contents ON set_contents.card_id = cards.id
WHERE
	circulation.owner = $1
GROUP BY
	set_contents.set_name;
"""

SEARCHTRADESBYCARDSANDUSER = """
SELECT 
	offers.trade_id 
FROM 
	tcg.trades
	INNER JOIN tcg.offers ON (trades.creator = offers.offerer AND trades.id = offers.trade_id)
	INNER JOIN tcg.circulation ON offers.item = circulation.id
	INNER JOIN tcg.cards ON cards.id = circulation.card
	INNER JOIN tcg.set_contents ON set_contents.card_id = circulation.card
WHERE
	offers.offerer = $1
	AND
	((cards.rarity::text ILIKE $2) OR (cards.name ILIKE $3) OR (set_contents.set_name ILIKE $2))
GROUP BY 
	offers.trade_id;
"""

SEARCHTRADESBYCARDS = """
SELECT 
	offers.trade_id 
FROM 
	tcg.trades
	INNER JOIN tcg.offers ON (trades.creator = offers.offerer AND trades.id = offers.trade_id)
	INNER JOIN tcg.circulation ON offers.item = circulation.id
	INNER JOIN tcg.cards ON cards.id = circulation.card
	INNER JOIN tcg.set_contents ON set_contents.card_id = circulation.card
WHERE
	((cards.rarity::text ILIKE $1) OR (cards.name ILIKE $2) OR (set_contents.set_name ILIKE $1))
GROUP BY 
	offers.trade_id;
"""

SEARCHTRADESBYUSER = """
SELECT 
	offers.trade_id
FROM 
	tcg.trades
	INNER JOIN tcg.offers ON (trades.creator = offers.offerer AND trades.id = offers.trade_id)
	INNER JOIN tcg.circulation ON offers.item = circulation.id
	INNER JOIN tcg.cards ON cards.id = circulation.card
	INNER JOIN tcg.set_contents ON set_contents.card_id = circulation.card
WHERE
	offers.offerer = $1
GROUP BY 
	offers.trade_id;
"""


SEARCHTRADESBYCURRENCY = """
SELECT 
	offers.trade_id 
FROM 
	tcg.trades
	INNER JOIN tcg.offers ON (trades.creator = offers.offerer AND trades.id = offers.trade_id)
WHERE
	offers.type = 'Currency' AND offers.item >= $1
GROUP BY 
	offers.trade_id;
"""


POKEDEXQUERY = """
SELECT
	cards.id,
	cards.name AS name,
	cards.rarity,
	cards.description,
	cards.picture AS picture,
	set_contents.set_name,
	sets.cover,
	c.cardsCount AS count
FROM 
	tcg.set_contents
	INNER JOIN tcg.cards ON set_contents.card_id = cards.id
	INNER JOIN tcg.sets ON sets.set_name = set_contents.set_name
	LEFT JOIN (SELECT card, COUNT(card) As cardsCount FROM tcg.circulation WHERE circulation.owner = $1 GROUP BY card) c ON c.card = cards.id
ORDER BY 
	cards.rarity DESC,
	cards.id;
"""

SEARCHPOKEDEX = """
SELECT
	cards.id,
	cards.name AS name,
	cards.rarity,
	cards.description,
	cards.picture AS picture,
	set_contents.set_name,
	sets.cover,
	c.cardsCount AS count
FROM 
	tcg.set_contents
	INNER JOIN tcg.cards ON set_contents.card_id = cards.id
	INNER JOIN tcg.sets ON sets.set_name = set_contents.set_name
	LEFT JOIN (SELECT card, COUNT(card) As cardsCount FROM tcg.circulation WHERE circulation.owner = $1 GROUP BY card) c ON c.card = cards.id
WHERE
	((cards.rarity::text ILIKE $2) OR (cards.name ILIKE $3) OR (set_contents.set_name ILIKE $2) OR (cards.description ILIKE $3))
ORDER BY 
	cards.rarity DESC,
	cards.id;
"""


SEARCHPOKEDEX = """
SELECT
	cards.id,
	cards.name AS name,
	cards.rarity,
	cards.description,
	cards.picture AS picture,
	set_contents.set_name,
	sets.cover,
	c.cardsCount AS count
FROM 
	tcg.set_contents
	INNER JOIN tcg.cards ON set_contents.card_id = cards.id
	INNER JOIN tcg.sets ON sets.set_name = set_contents.set_name
	LEFT JOIN (SELECT card, COUNT(card) As cardsCount FROM tcg.circulation WHERE circulation.owner = $1 GROUP BY card) c ON c.card = cards.id
WHERE
	((cards.rarity::text ILIKE $2) OR (cards.name ILIKE $3) OR (set_contents.set_name ILIKE $2) OR (cards.description ILIKE $3))
ORDER BY 
	cards.rarity DESC,
	cards.id;
"""

#endregion

#region stats
MAPSTATWINS = """
select count(wins.map_winner) from 
    (select distinct match_stats.match_id, match_stats.map_name, match_stats.map_winner, match_stats.map_loser, player_stats.map_type 
	from stats.match_stats, stats.player_stats 
    where player_stats.esports_match_id = match_stats.match_id 
	and player_stats.map_name = match_stats.map_name 
	and EXTRACT(year from round_start_time) = $1 
	and player_stats.map_type = $3 
	and map_winner = $2) 
as wins
"""

MAPSTATLOSS = """
select count(loss.map_loser) from 
    (select distinct match_stats.match_id, match_stats.map_name, match_stats.map_winner, match_stats.map_loser, player_stats.map_type 
	from stats.match_stats, stats.player_stats 
    where player_stats.esports_match_id = match_stats.match_id 
	and player_stats.map_name = match_stats.map_name 
	and EXTRACT(year from round_start_time) = $1 
	and player_stats.map_type = $3 
	and map_loser = $2) 
as loss
"""


STAT = """
select per10, r from (
	--Sorting data and ranking--
	select player_name, (sum(stat_amount) / (time/600) ) as per10, rank() over (order by (sum(stat_amount) / (time/600) ) desc) as r from 
	--Getting rest of data with timeplayed included--
	( 
		select distinct p.player_name, p.team_name, p.esports_match_id, p.map_name, p.stat_amount, i.role, timeplayed.count as time
		from stats.player_stats as p, 
		stats.playerinfo as i, 
		--Getting Time Played Here--
			(
				select player_name, sum(stat_amount) as count
				from stats.player_stats
				where stat_name = 'Time Played'
				and hero_name = $4
				and EXTRACT(year from start_time) = $1
				group by player_name
			) as timeplayed
		where EXTRACT(year from p.start_time) = $1
		and p.player_name = i.name
		and p.player_name = timeplayed.player_name
		and stat_name = $3 
		and hero_name = $4
	) as y 
	where (time / 60) > 30
	group by player_name, time
	order by per10 desc
) as q
where lower(player_name) = $2
"""

STATWIN = """
select count, rank from (
	select match_winner, count(match_winner) as count, rank() over (order by count(match_winner) desc) as rank from ( 
		select DISTINCT match_id, match_winner 
		from stats.match_stats 
		where EXTRACT(year from round_start_time) = $1 
		order by match_id
	) as x 
	group by match_winner
) as y 
where match_winner = $2
"""

STATLOSS = """
select coalesce(
	(select count(match_loser) from ( 
		select DISTINCT match_id,
		case when 
			match_winner = team_one_name then team_two_name 
			else team_one_name 
		end AS match_loser 
		from stats.match_stats 
		where EXTRACT(year from round_start_time) = $1 
		order by match_id
	) as x 
	where match_loser = $2 
	group by match_loser
	),0
) 
"""
STATLB = """
select player_name, per10, r from (
	--Sorting data and ranking--
	select player_name, (sum(stat_amount) / (time/600) ) as per10, rank() over (order by (sum(stat_amount) / (time/600) ) desc) as r from 
	--Getting rest of data with timeplayed included--
	( 
		select distinct p.player_name, p.team_name, p.esports_match_id, p.map_name, p.stat_amount, i.role, timeplayed.count as time
		from stats.player_stats as p, 
		stats.playerinfo as i, 
		--Getting Time Played Here--
			(
				select player_name, sum(stat_amount) as count
				from stats.player_stats
				where stat_name = 'Time Played'
				and hero_name = $2
				and EXTRACT(year from start_time) = $1
				group by player_name
			) as timeplayed
		where EXTRACT(year from p.start_time) = $1
		and p.player_name = i.name
		and p.player_name = timeplayed.player_name
		and stat_name = $3 
		and hero_name = $2
	) as y 
	where (time / 60) > 30
	group by player_name, time
	order by per10 desc
) as q

"""

STATLIST = """
select DISTINCT(stat_name), hero_name
FROM stats.player_stats
WHERE lower(hero_name) = $1
ORDER BY stat_name
"""


MAP5WINS = """
select count(map_winner) from ( 	
	select DISTINCT(match_id), stage, game_number, match_winner, map_winner, map_loser, map_name
	from stats.match_stats
	where game_number=5
	and (map_winner = $2
	or map_loser = $2)
	and EXTRACT(year from round_start_time) = $1
) as q
where map_winner = $2
"""

MAP5LOSS = """
select count(map_winner) from ( 	
	select DISTINCT(match_id), stage, game_number, match_winner, map_winner, map_loser, map_name
	from stats.match_stats
	where game_number=5
	and (map_winner = $2
	or map_loser = $2)
	and EXTRACT(year from round_start_time) = $1
) as q
where map_loser = $2
"""

#endregion

#region misc
STARSTATS = """
WITH starboard AS (
SELECT 
	reactions.message AS msg_id,
    count(reactions.message) AS stars,
    messages.author
FROM 
	discord.reactions,
    discord.messages
WHERE reactions.name = chr(11088) 
AND reactions.message = messages.id
AND messages.timestamp < '2021-06-03'
GROUP BY reactions.message, messages.author, messages.timestamp
HAVING count(reactions.message) >= 6
UNION
SELECT 
	message as msg_id,
	count as stars,
	author
FROM
	discord.starboard
	
)
SELECT 
	round(avg(starboard.stars), 0) as averagestars, 
	count(starboard.msg_id), 
	max(starboard.stars), 
	sum(starboard.stars) as totalrecieved 
FROM
	starboard
WHERE
	author = $1
"""

RANDOMSTARPOST = """
WITH starboard AS (
	SELECT 
		reactions.message AS msg_id,
		count(reactions.message) AS stars,
		messages.author,
		messages.channel
	FROM 
		discord.reactions,
		discord.messages
	WHERE 
		reactions.name = chr(11088) 
		AND reactions.message = messages.id
		AND messages.timestamp < '2021-06-03'
	GROUP BY 
		reactions.message, 
		messages.author, 
		messages.timestamp, 
		messages.channel
	HAVING 
		count(reactions.message) >= 6

	UNION

	SELECT 
		message as msg_id,
		count as stars,
		author,
		channel
	FROM
		discord.starboard
	)
SELECT 
	starboard.msg_id as message, 
	starboard.stars as count,
	starboard.channel as channel  
FROM 
	starboard
WHERE
	author = $1
ORDER BY 
	RANDOM()
LIMIT 1
"""

ALLUSERRANDOMSTARPOST = """
WITH starboard AS (
	SELECT 
		reactions.message AS msg_id,
		count(reactions.message) AS stars,
		messages.author,
		messages.channel
	FROM 
		discord.reactions,
		discord.messages
	WHERE 
		reactions.name = chr(11088) 
		AND reactions.message = messages.id
		AND messages.timestamp < '2021-06-03'
	GROUP BY 
		reactions.message, 
		messages.author, 
		messages.timestamp, 
		messages.channel
	HAVING 
		count(reactions.message) >= 6

	UNION

	SELECT 
		message as msg_id,
		count as stars,
		author,
		channel
	FROM
		discord.starboard
	)
SELECT 
	starboard.msg_id as message, 
	starboard.stars as count,
	starboard.channel as channel  
FROM 
	starboard
ORDER BY 
	RANDOM()
LIMIT 1
"""

TOPSTARPOST = """ 
WITH starboard AS (
	SELECT 
		reactions.message AS msg_id,
		count(reactions.message) AS stars,
		messages.author,
		messages.channel
	FROM 
		discord.reactions,
		discord.messages
	WHERE 
		reactions.name = chr(11088) 
		AND reactions.message = messages.id
		AND messages.timestamp < '2021-06-03'
	GROUP BY 
		reactions.message, 
		messages.author, 
		messages.timestamp, 
		messages.channel
	HAVING 
		count(reactions.message) >= 6

	UNION

	SELECT 
		message as msg_id,
		count as stars,
		author,
		channel
	FROM
		discord.starboard
	)
select 
	max(starboard.stars) as max, 
	starboard.msg_id as message,
	starboard.channel as channel
from 
	starboard
where 
	author = $1
group by 
	stars, 
	msg_id,
	channel
order by 
	max desc
LIMIT 1


"""

STARBOARDCOUNT = """
WITH starboard AS (
	SELECT 
		reactions.message AS msg_id,
		count(reactions.message) AS stars,
		messages.author,
		messages.channel
	FROM 
		discord.reactions,
		discord.messages
	WHERE 
		reactions.name = chr(11088) 
		AND reactions.message = messages.id
		AND messages.timestamp < '2021-06-03'
	GROUP BY 
		reactions.message, 
		messages.author, 
		messages.timestamp, 
		messages.channel
	HAVING 
		count(reactions.message) >= 6

	UNION

	SELECT 
		message as msg_id,
		count as stars,
		author,
		channel
	FROM
		discord.starboard
)
select count(msg_id)
from starboard
"""
#endregion

#region stocks
SELLPORTFOLIO = """
SELECT 
	portfolio.teamshort, 
	totalprice,
	initprice, 
	count, 
	datebought
FROM 
	economy.portfolio as portfolio 
WHERE
	portfolio.teamshort = $1
AND
	portfolio.userid = $2
ORDER BY
	datebought ASC
;
"""
#endregion