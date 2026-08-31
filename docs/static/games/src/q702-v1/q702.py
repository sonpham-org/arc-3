"""q702 Semaphore Evidence -- stop only after reliability-weighted relay evidence is decisive."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,YARD,CLIFF,FLAG,BEAM,SAMPLE,MARGIN,GOAL,BAD=9,10,3,14,11,6,12,13,15
LEVELS=[{"name":"Visible Sample","seq":(1,)},{"name":"Weak Relay","seq":(2,1)},{"name":"Reliability Shift","seq":(3,1,2)},{"name":"Miniature Test","seq":(4,2,1,3)},{"name":"Decisive Margin","seq":(2,3,1,4,2,1)},{"name":"Semaphore Evidence","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 beam,reliability,evidence,margin,cost,tests,stopped=s
 if a==1:w=1+reliability;margin+=w;evidence=evidence+((beam,w,1),);cost+=1;beam=(beam+1)%4
 elif a==2:w=max(1,3-reliability);margin-=w;evidence=evidence+((beam,w,-1),);cost+=2;beam=(beam+2)%4
 elif a==3:reliability=(reliability+1+beam%2)%3;margin+=1 if reliability==2 else 0
 elif a==4:outcome=(margin+beam+reliability)%3;tests=tests+(outcome,);margin+=outcome-1;cost+=1
 elif a==5:stopped=(beam,reliability,evidence[-5:],margin,cost,tests[-3:])
 return beam,reliability,evidence,margin,cost,tests,stopped
for x in LEVELS:
 s=(0,0,(),0,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=YARD;f[7:31,7:57]=CLIFF
  for i in range(4):x=9+i*13;f[11:27,x:x+9]=BEAM;f[13+i%2*6:19+i%2*6,x+2:x+7]=FLAG if i==g.beam else SAMPLE
  for i,(_,w,sign) in enumerate(g.evidence[-5:]):x=7+i*10;f[35:42,x:x+8]=SAMPLE if sign>0 else BEAM;f[43:46,x:x+2+w*2]=FLAG
  center=31;lo=min(center,center+g.margin*3);hi=max(center,center+g.margin*3);f[49:54,max(6,lo):min(58,hi+1)]=MARGIN
  for i,v in enumerate(g.tests[-3:]):f[56:60,8+i*13:16+i*13]=FLAG if v>1 else BEAM
  if g.stopped:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q702(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q702",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.beam=self.reliability=self.margin=self.cost=0;self.evidence=self.tests=();self.stopped=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.beam,self.reliability,self.evidence,self.margin,self.cost,self.tests,self.stopped=advance((self.beam,self.reliability,self.evidence,self.margin,self.cost,self.tests,self.stopped),a)
  elif a==6:
   if (self.beam,self.reliability,self.evidence,self.margin,self.cost,self.tests,self.stopped)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
