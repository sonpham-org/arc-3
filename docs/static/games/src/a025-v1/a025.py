"""a025 Which Hand -- infer which identical cursor is causally controlled."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,ROOM,TRACK,CURSOR,DECOY,PROBE,SWITCH,GOAL,BAD=4,10,8,14,12,6,11,13,15
LEVELS=[{"name":"Neutral Probe","seq":(1,3)},{"name":"Second Motion","seq":(2,3)},{"name":"Agency Contrast","seq":(1,2,3)},{"name":"Autonomous Rule","seq":(4,2,1,3)},{"name":"Irreversible Switch","seq":(2,3,1,4,2,1,3)},{"name":"Which Hand","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 cursors,controlled,tick,probes,switches,bound=s;c=list(cursors)
 if a==1:c[controlled]=(c[controlled]+1)%10;c[controlled^1]=(c[controlled^1]+tick%2)%10
 elif a==2:c[controlled]=(c[controlled]-1)%10;c[controlled^1]=(c[controlled^1]+2)%10
 elif a==3:probes=probes+((tuple(c),controlled,tick),)
 elif a==4:tick+=1;c[controlled^1]=(c[controlled^1]+tick)%10;switches=(switches+((c[0]+c[1])%5,))[-3:]
 elif a==5:bound=(tuple(c),controlled,tick,probes[-4:],switches)
 return tuple(c),controlled,tick,probes,switches,bound
for x in LEVELS:
 s=((1,7),0,0,(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=ROOM
  for lane,p in enumerate(g.cursors):y=10+lane*17;f[y:y+10,7:57]=TRACK;x=8+p*5;f[y+1:y+9,x:x+5]=CURSOR if lane==g.controlled else DECOY
  for i,_ in enumerate(g.probes[-4:]):f[42:48,8+i*12:17+i*12]=PROBE
  for i,v in enumerate(g.switches):f[51:56,8+i*14:18+i*14]=SWITCH
  if g.bound:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A025(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a025",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.cursors=(1,7);self.controlled=0;self.tick=0;self.probes=self.switches=();self.bound=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.cursors,self.controlled,self.tick,self.probes,self.switches,self.bound=advance((self.cursors,self.controlled,self.tick,self.probes,self.switches,self.bound),a)
  elif a==6:
   if (self.cursors,self.controlled,self.tick,self.probes,self.switches,self.bound)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
