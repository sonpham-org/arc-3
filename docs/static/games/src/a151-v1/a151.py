"""a151 Delayed Agency -- attribute tagged commands across heterogeneous device delays."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,LAB,DEVICE,TAG_A,TAG_B,QUEUE,EFFECT,CURSOR,MATCH,MISMATCH=2,8,7,12,14,10,13,11,4,6
BAD=15
DELAYS=(1,3,2)
LEVELS=[
 {"name":"Issue Tagged Command","seq":(1,)},{"name":"Select Control","seq":(2,)},
 {"name":"Advance Clock","seq":(3,1)},{"name":"Match Delayed Effect","seq":(1,2,3,4,2)},
 {"name":"Separate Devices","seq":(1,3,2,1,4,3,2)},{"name":"Delayed Agency","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 timers,tags,cursor,clock,effects,matches,mismatches,history,snapshot=s;tm=list(timers);tg=list(tags);ef=list(effects)
 if a==1:tm[cursor]=DELAYS[cursor];tg[cursor]=1-tg[cursor];history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%3;history=(history+(2,))[-8:]
 elif a==3:
  clock=(clock+1)%8
  for i in range(3):
   if tm[i]>0:tm[i]-=1
   if tm[i]==0:ef[i]=tg[i]
  history=(history+(3,))[-8:]
 elif a==4:matches=sum(int(ef[i]==tg[i] and tm[i]==0) for i in range(3));mismatches=3-matches;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(tm),tuple(tg),cursor,clock,tuple(ef),matches,mismatches,history)
 return tuple(tm),tuple(tg),cursor,clock,tuple(ef),matches,mismatches,history,snapshot
for q in LEVELS:
 s=((0,0,0),(0,1,0),0,0,(0,1,0),3,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAB
  for i in range(3):
   x=9+i*18;f[15:45,x:x+14]=DEVICE;f[18:27,x+3:x+11]=TAG_A if g.tags[i]==0 else TAG_B;f[31:40,x+3:x+11]=TAG_A if g.effects[i]==0 else EFFECT
   f[11:14,x:x+g.timers[i]*4]=QUEUE
   if i==g.cursor:f[47:50,x:x+14]=CURSOR
  f[54:58,8:8+g.matches*12]=MATCH;f[7:10,8:8+g.mismatches*12]=MISMATCH
  if g.bad:f[1:4,18:46]=BAD
  return f
class A151(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a151",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.timers,self.tags,self.cursor,self.clock,self.effects,self.matches,self.mismatches,self.history,self.snapshot=((0,0,0),(0,1,0),0,0,(0,1,0),3,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.timers,self.tags,self.cursor,self.clock,self.effects,self.matches,self.mismatches,self.history,self.snapshot=advance((self.timers,self.tags,self.cursor,self.clock,self.effects,self.matches,self.mismatches,self.history,self.snapshot),a)
  elif a==6:
   if (self.timers,self.tags,self.cursor,self.clock,self.effects,self.matches,self.mismatches,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
