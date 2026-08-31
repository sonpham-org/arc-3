"""q704 Tessera Evidence -- weigh seam evidence and interrupt a folding macro before stopping."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,MOSAIC,TILE,SEAM,SAMPLE,RELIABLE,WINDOW,GOAL,BAD=0,10,14,8,6,12,11,13,15
LEVELS=[{"name":"One Seam","seq":(1,)},{"name":"Weak Tessera","seq":(2,1)},{"name":"Fold Reliability","seq":(3,1,2)},{"name":"Interrupt Window","seq":(4,2,1,3)},{"name":"Stable Margin","seq":(2,3,1,4,2,1)},{"name":"Tessera Evidence","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 seam,reliability,phase,samples,margin,interrupt,stopped=s
 if a==1:w=1+reliability;margin+=w;samples=samples+((seam,w,1),);seam=(seam+1+phase)%4
 elif a==2:w=max(1,3-reliability);margin-=w;samples=samples+((seam,w,-1),);seam=(seam+2)%4
 elif a==3:phase=(phase+1)%5;reliability=(reliability+int(phase in (1,3))+seam)%3
 elif a==4:interrupt=(phase,seam,reliability);phase=(phase+2)%5;margin+=1 if interrupt[0]==3 else -1
 elif a==5:stopped=(seam,reliability,phase,samples[-5:],margin,interrupt)
 return seam,reliability,phase,samples,margin,interrupt,stopped
for x in LEVELS:
 s=(0,0,0,(),0,None,None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=MOSAIC
  for i in range(9):x=8+(i%3)*16;y=8+(i//3)*9;f[y:y+7,x:x+13]=TILE;f[y:y+7,x+5:x+7]=SEAM if i%4==g.seam else RELIABLE
  for i,(_,w,sign) in enumerate(g.samples[-5:]):x=7+i*10;f[37:43,x:x+8]=SAMPLE if sign>0 else SEAM;f[44:47,x:x+2+w*2]=RELIABLE
  f[50:54,8:8+g.phase*9+7]=WINDOW;center=31;lo=min(center,center+g.margin*3);hi=max(center,center+g.margin*3);f[56:60,max(6,lo):min(58,hi+1)]=RELIABLE
  if g.stopped:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class Q704(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q704",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.seam=self.reliability=self.phase=self.margin=0;self.samples=();self.interrupt=self.stopped=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.seam,self.reliability,self.phase,self.samples,self.margin,self.interrupt,self.stopped=advance((self.seam,self.reliability,self.phase,self.samples,self.margin,self.interrupt,self.stopped),a)
  elif a==6:
   if (self.seam,self.reliability,self.phase,self.samples,self.margin,self.interrupt,self.stopped)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
