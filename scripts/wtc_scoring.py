"""Official 11th-edition Warhammer Teams VP differential to 20 Battle Points.
Source: Games Workshop, Warhammer 40,000 Teams Event Companion, Team Scoring.
Works on *final* integer victory points already inclusive of any awarded VP.
A close VP victory (margin 1-5) yields 10-10 BP but remains a singles win.
"""
def wtc_battle_points(vp_a, vp_b):
    a,b=int(vp_a),int(vp_b)
    if a<0 or b<0 or a>100 or b>100:
        raise ValueError("Final VP must be between 0 and 100 inclusive")
    difference=abs(a-b)
    if difference<=5:
        winner=10
    elif difference>=51:
        winner=20
    else:
        winner=10+(difference+4)//5
    return (winner,20-winner) if a>=b else (20-winner,winner)

def win_draw_loss_from_vp(vp_a,vp_b):
    a,b=int(vp_a),int(vp_b)
    return "win" if a>b else "loss" if a<b else "draw"

if __name__=="__main__":
    for delta,want in [(0,10),(5,10),(6,11),(10,11),(11,12),(15,12),(16,13),(50,19),(51,20),(100,20)]:
        got=wtc_battle_points(100,100-delta)
        assert got==(want,20-want),(delta,got)
        assert wtc_battle_points(100-delta,100)==(20-want,want)
    assert win_draw_loss_from_vp(86,82)=="win"
    assert wtc_battle_points(86,82)==(10,10)
    print("11th-edition WTC BP conversion boundaries verified")
