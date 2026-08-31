"""a008 Cascade Autopsy -- freeze replays to find an early deviation behind later alarms."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,THEATER,EVENT,ALARM,DEVIATION,FREEZE,REPLAY,GOAL,BAD=7,10,8,14,11,6,12,13,15
LEVELS=[{"name":"First Replay","seq":(1,3)},{"name":"Later Freeze","seq":(2,3)},{"name":"Alarm Delay","seq":(1,2,3)},{"name":"Speed Change","seq":(4,2,1,3)},{"name":"Causal Mark","seq":(2,3,1,4,2,1,3)},{"name":"Cascade Autopsy","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 cursor,speed,cause,replays,freezes,replaced=s
 if a==1:cursor=(cursor+1*speed)%10
 elif a==2:cursor=(cursor+3*speed)%10
 elif a==3:events=tuple(2 if i==cause else 1 if i>cause+2 else 0 for i in range(10));freezes=freezes+((cursor,events[cursor]),);replays=replays+((speed,cursor,events),)
 elif a==4:speed=2 if speed==1 else 1;cursor=(cursor+speed)%10
 elif a==5:replaced=(cause,cursor,speed,replays[-4:],freezes[-4:])
 return cursor,speed,cause,replays,freezes,replaced
for x in LEVELS:
 s=(0,1,3,(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=THEATER;events=g.replays[-1][2] if g.replays else (0,)*10
  for i,v in enumerate(events):x=7+(i%5)*11;y=9+(i//5)*14;f[y:y+10,x:x+9]=EVENT if v==0 else DEVIATION if v==2 else ALARM;f[y+3:y+7,x+3:x+6]=FREEZE if i==g.cursor else REPLAY
  for i,(p,v) in enumerate(g.freezes[-4:]):x=8+i*12;f[40:46,x:x+9]=FREEZE;f[47:50,x:x+2+p%6]=DEVIATION if v==2 else ALARM
  f[53:57,8:8+g.speed*18]=REPLAY
  if g.replaced:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A008(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a008",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.cursor=0;self.speed=1;self.cause=3;self.replays=self.freezes=();self.replaced=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.cursor,self.speed,self.cause,self.replays,self.freezes,self.replaced=advance((self.cursor,self.speed,self.cause,self.replays,self.freezes,self.replaced),a)
  elif a==6:
   if (self.cursor,self.speed,self.cause,self.replays,self.freezes,self.replaced)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
