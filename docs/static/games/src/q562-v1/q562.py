"""q562 Tide Counter -- shape a rival before opening an irreversible tidal sluice."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,WATER,SHELL,CURRENT,TACTIC0,TACTIC1,TACTIC2,EVIDENCE,SLUICE,GOAL,BAD=2,10,11,14,6,9,12,7,5,13,15
LEVELS=[
 {"name":"Two Treatments","seq":(1,2)},{"name":"Repeated Shell","seq":(1,1)},
 {"name":"Reversed Current","seq":(1,3,2)},{"name":"Shaped Tide","seq":(2,1,2)},
 {"name":"Delayed Sluice","seq":(1,2,3,2,1)},{"name":"Tide Counter","seq":(2,1,3,2,2,1,3)}]
def advance(s,a,x):
 recent,current,pos,rival,evidence,opened,exploited=s
 if a in (1,2):
  p=a-1;recent=(recent+(p,))[-2:];pos=(pos+a+current)%10;rival=(sum((i+1)*v for i,v in enumerate(recent))+current+int(len(recent)==2 and recent[0]==recent[1]))%3;evidence=evidence+(rival,)
 elif a==3:current^=1;rival=(rival+1)%3
 elif a==4:
  if len(evidence)<2 or rival!=x["goal"]:return None
  opened=(rival,current,pos)
 elif a==5:
  if opened is None:return None
  exploited=(opened,tuple(recent),len(evidence))
 return recent,current,pos,rival,evidence,opened,exploited
for x in LEVELS:
 s=((),0,0,0,(),None,None)
 for a in x["seq"]:s=advance(s,a,x);assert s is not None
 x["goal"]=s[3];x["plan"]=x["seq"]+(4,5)
def target(x):
 s=((),0,0,0,(),None,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=WATER
  for i in range(10):x=8+i*5;f[10:17,x:x+4]=SHELL if i==g.pos else CURRENT
  cols=(TACTIC0,TACTIC1,TACTIC2)
  for i,c in enumerate(cols):f[25:39,8+i*18:22+i*18]=c if i==g.rival else EVIDENCE
  for i,v in enumerate(g.evidence[-5:]):f[45:50,8+i*9:14+i*9]=cols[v]
  f[53:58,8:29]=SLUICE;f[53:58,35:56]=CURRENT
  if g.opened:f[53:58,8:29]=GOAL
  if g.exploited:f[55:59,39:56]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q562(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self.cfg=LEVELS[0];self._reset();self.target=target(self.cfg);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q562",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.recent=();self.current=self.pos=self.rival=0;self.evidence=();self.opened=self.exploited=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=target(self.cfg)
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.recent,self.current,self.pos,self.rival,self.evidence,self.opened,self.exploited),a,self.cfg)
   if s is None:self.bad=True;self.lose()
   else:self.recent,self.current,self.pos,self.rival,self.evidence,self.opened,self.exploited=s
  elif a==6:
   if (self.recent,self.current,self.pos,self.rival,self.evidence,self.opened,self.exploited)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
